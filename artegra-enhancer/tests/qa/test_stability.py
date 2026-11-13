"""CPU-only service endurance and recovery; all images and engine events are synthetic."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import socket
import time

import numpy as np
from PIL import Image
import pytest

from tests.qa.service_process import ServiceProcess, complete, port_open, wait_for
from tests.service.helpers import gradient


@pytest.fixture
def services(tmp_path):
    owned = []
    def make(*, env=None, state="state", preferred_port=18950):
        service = ServiceProcess(tmp_path / state, env=env, preferred_port=preferred_port,
                                 output=tmp_path / "output")
        owned.append(service)
        return service.start()
    yield make
    for service in reversed(owned):
        service.close()


def inputs(folder, count=3):
    """Odd-sized RGB/RGBA/JPEG fixtures with orientation and no external assets."""
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(count):
        width, height = 79 + index % 7, 67 + index % 5
        pixels = gradient(width, height, index)
        suffix = ".jpg" if index % 3 == 0 else ".png"
        path = folder / f"synthetic-{index:03d}{suffix}"
        if index % 3 == 1:
            alpha = np.tile(np.linspace(0, 255, width).astype(np.uint8), (height, 1))
            Image.fromarray(np.dstack((pixels, alpha))).save(path)
        elif suffix == ".jpg":
            exif = Image.Exif()
            exif[0x0112] = 6
            Image.fromarray(pixels).save(path, quality=91, exif=exif)
        else:
            Image.fromarray(pixels).save(path)
        paths.append(path)
    return paths


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_outputs(job, scale=2):
    assert job["state"] == "done", job
    for item in job["items"]:
        assert item["state"] == "done", item
        assert item["result_ready"]
        path = Path(item["output"])
        with Image.open(path) as result:
            assert result.size == tuple(side * scale for side in item["size"])
            assert (result.mode == "RGBA") == item["alpha"]
            result.load()
        sidecar = json.loads(Path(item["sidecar"]).read_text(encoding="utf8"))
        assert sidecar["output"]["sha256"] == digest(path)
        assert (sidecar["job"], sidecar["item"]) == (job["id"], item["id"])


def test_real_http_auth_port_fallback_and_cleanup(services):
    blocker = socket.socket()
    port = next((number for number in range(18950, 18970) if not port_open(number)), None)
    assert port is not None, "test needs one free port in the reserved service range"
    blocker.bind(("127.0.0.1", port))
    blocker.listen()
    try:
        service = services(preferred_port=port)
        assert service.port != port
        assert service.get("/health", auth=False)[0] == 401
        assert service.get("/health", headers={"Authorization": "Bearer " + "x" * 64})[0] == 401
        assert service.get("/health", headers={"Origin": "https://example.test"})[0] == 403
        assert service.get("/health", headers={"Host": "example.test"})[0] == 403
        assert service.get("/health?token=" + service.token, auth=False)[0] == 401
        # An invalid request must not poison the next authenticated connection.
        assert service.post("/api/settings", {"idle_minutes": -1})[0] == 400
        assert service.get("/health")[0] == 200
        chosen = service.port
        service.shutdown()
        wait_for(lambda: not port_open(chosen), message="owned listener was left open")
        assert not service.token_path.exists()
        assert port_open(port), "shutdown touched the unrelated blocked port"
    finally:
        blocker.close()


def test_fifty_images_mixed_modes_integrity_and_latency(services, tmp_path):
    service = services()
    # Keep this a service/batch test, with no UI, live canvas, notifications, or GPU.
    assert service.post("/api/settings", {"split": False, "detailed_preview": False, "notify": False})[0] == 200
    paths = inputs(tmp_path / "input", 50)
    originals = {p: digest(p) for p in paths}
    start = time.monotonic()
    media = service.add(paths)
    standard = service.job([m["id"] for m in media[:25]], {"scale": 2, "mode": "standard"})
    fast = service.job([m["id"] for m in media[25:]], {"scale": 2, "mode": "fast"})
    latencies = []
    while True:
        tick = time.monotonic()
        code, health, _ = service.get("/health")
        latencies.append(time.monotonic() - tick)
        assert code == 200 and "engine" in health
        code, standard, _ = service.get("/api/jobs/" + standard["id"])
        assert code == 200
        code, fast, _ = service.get("/api/jobs/" + fast["id"])
        assert code == 200
        if complete(standard) and complete(fast):
            break
        assert time.monotonic() - start < 180, "50-image synthetic batch exceeded 180 seconds"
        time.sleep(.1)
    elapsed = time.monotonic() - start
    for job in (standard, fast):
        assert_outputs(job)
        assert job["summary"]["progress"] == 1.0
    assert len({i["output"] for j in (standard, fast) for i in j["items"]}) == 50
    assert len([r for r in service.renders() if r["status"] == "success"]) == 50
    assert all(digest(p) == expected for p, expected in originals.items()), "input image was changed"
    assert max(latencies) < 5, "health API stopped responding during the batch"
    service.shutdown()
    metrics = {"images": 50, "standard": 25, "fast": 25, "seconds": round(elapsed, 3),
               "health_max_ms": round(max(latencies) * 1000, 1),
               "health_median_ms": round(float(np.median(latencies)) * 1000, 1),
               "peak_owned_process_bytes": service.peak_bytes, "engine": "synthetic", "gpu_used": False}
    print("\nCPU_BATCH_METRICS=" + json.dumps(metrics, sort_keys=True))
    report = os.environ.get("PILOT_QA_REPORT")
    if report:
        target = Path(report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf8")


def test_restart_idempotency_keeps_completed_output_and_never_overwrites(services, tmp_path):
    service = services()
    media = service.add(inputs(tmp_path / "input", 1))
    request_id = secrets.token_hex(16)
    job = service.wait_job(service.job([media[0]["id"]], request_id=request_id)["id"])
    assert_outputs(job)
    item = job["items"][0]
    before = (digest(item["output"]), Path(item["output"]).stat().st_mtime_ns,
              digest(item["sidecar"]), Path(item["sidecar"]).stat().st_mtime_ns)
    assert service.job([media[0]["id"]], request_id=request_id)["id"] == job["id"]
    service.shutdown()
    service = services()
    assert service.job([media[0]["id"]], request_id=request_id)["id"] == job["id"]
    assert service.get("/api/inputs")[1]["items"][0]["id"] == media[0]["id"]
    mismatch = {"client_request_id": request_id, "media_ids": [media[0]["id"]], "settings": {"scale": 4}}
    assert service.post("/api/jobs", mismatch)[0] == 409
    repeat = service.wait_job(service.job([media[0]["id"]])["id"])
    assert_outputs(repeat)
    assert repeat["items"][0]["output"] != item["output"]
    assert (digest(item["output"]), Path(item["output"]).stat().st_mtime_ns,
            digest(item["sidecar"]), Path(item["sidecar"]).stat().st_mtime_ns) == before
    assert len(list((tmp_path / "output").glob("*.png"))) == 2


def test_concurrent_duplicate_submission_creates_exactly_one_job(services, tmp_path):
    service = services(env={"CU_FAKE_STAGE_SECONDS": "0.3"})
    media = service.add(inputs(tmp_path / "input", 1))[0]
    request_id = secrets.token_hex(16)
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: service.job([media["id"]], request_id=request_id), range(8)))
    assert len({reply["id"] for reply in replies}) == 1
    result = service.wait_job(replies[0]["id"])
    assert_outputs(result)
    assert len(service.get("/api/jobs")[1]["jobs"]) == 1
    assert len(service.renders()) == 1
    assert len(list((tmp_path / "output").glob("*.png"))) == 1


def test_restart_after_publish_keeps_the_existing_result(services, tmp_path):
    service = services()
    media = service.add(inputs(tmp_path / "input", 1))[0]
    job = service.wait_job(service.job([media["id"]])["id"])
    item = job["items"][0]
    before = (digest(item["output"]), digest(item["sidecar"]))
    count = len(service.renders())
    service.shutdown()
    # Recreate the persisted boundary after publishing but before the final
    # state change. The real restart recovery must recognize its own sidecar.
    record_path = service.state / "jobs" / (job["id"] + ".json")
    record = json.loads(record_path.read_text(encoding="utf8"))
    record["state"] = "running"
    record["items"][0]["state"] = "finishing"
    record_path.write_text(json.dumps(record), encoding="utf8")
    restarted = services()
    recovered = restarted.wait_job(job["id"])
    assert recovered["items"][0]["output"] == item["output"]
    assert (digest(item["output"]), digest(item["sidecar"])) == before
    assert len(restarted.renders()) == count
    assert len(list((tmp_path / "output").glob("*.png"))) == 1


@pytest.mark.parametrize("fault,scale", [("crash@1", 4), ("finish", 4)])
def test_abrupt_service_crash_resumes_without_rerender(services, tmp_path, fault, scale):
    env = {"CU_FAKE_FAULT": fault} if fault != "finish" else {"CU_TEST_CRASH": "finish"}
    service = services(env=env)
    media = service.add(inputs(tmp_path / "input", 2))
    job = service.job([m["id"] for m in media], {"scale": scale})
    assert service.wait_exit() == 70
    on_disk = json.loads((service.state / "jobs" / (job["id"] + ".json")).read_text(encoding="utf8"))
    assert on_disk["items"][0]["state"] in {"running", "finishing"}
    service.close()
    restarted = services(env=env)
    result = restarted.wait_job(job["id"])
    assert_outputs(result, scale=scale)
    renders = [r for r in restarted.renders() if r["status"] == "success"]
    assert len(renders) == 4, renders
    assert sorted(r["stage"] for r in renders) == [0, 0, 1, 1]
    assert len(list((tmp_path / "output").glob("*.png"))) == 2


def test_cancel_queued_and_running_then_next_job_succeeds(services, tmp_path):
    service = services(env={"CU_FAKE_STAGE_SECONDS": "1.5"})
    media = service.add(inputs(tmp_path / "input", 3))
    job = service.job([m["id"] for m in media])
    job = service.wait_job(job["id"], lambda j: j["items"][0]["state"] == "running")
    assert service.post(f'/api/jobs/{job["id"]}/items/i003/cancel')[1]["items"][2]["state"] == "cancelled"
    assert service.post(f'/api/jobs/{job["id"]}/cancel')[0] == 200
    stopped = service.wait_job(job["id"])
    assert [item["state"] for item in stopped["items"]] == ["cancelled"] * 3
    assert not list((tmp_path / "output").glob("*.png"))
    wait_for(lambda: not (service.state / "work" / job["id"]).exists())
    result = service.wait_job(service.job([media[0]["id"]])["id"])
    assert_outputs(result)


def test_faults_are_contained_and_following_item_succeeds(services, tmp_path):
    faults = "nows,reject@i001_s0,nofile@i002_s0,badsize@i003_s0,oom@i004_s0"
    service = services(env={"CU_FAKE_FAULT": faults})
    media = service.add(inputs(tmp_path / "input", 1))[0]
    job = service.wait_job(service.job([media["id"]] * 5)["id"])
    assert [i["state"] for i in job["items"]] == ["failed"] * 4 + ["done"]
    expected = ("could not accept", "result file is missing", "wrong size", "graphics card ran out of memory")
    for item, message in zip(job["items"], expected):
        assert message in item["error"]["text"]
        assert len(item["error"]["log_ref"]) == 8
        assert not item["output"]
    assert Path(job["items"][4]["output"]).is_file()
    assert service.get("/health")[1]["engine"]["workers"][0]["starts"] == 1


def test_separate_worker_crash_recovers_and_process_tree_closes(services, tmp_path):
    service = services(env={"CU_FAKE_PROCESS": "1", "CU_FAKE_FAULT": "crash@0"})
    media = service.add(inputs(tmp_path / "input", 1))[0]
    job = service.wait_job(service.job([media["id"]] * 2)["id"])
    assert [item["state"] for item in job["items"]] == ["failed", "done"]
    assert "closed unexpectedly" in job["items"][0]["error"]["text"]
    assert "70" in job["items"][0]["error"]["text"]
    assert Path(job["items"][1]["output"]).is_file()
    assert service.get("/health")[1]["engine"]["workers"][0]["starts"] >= 2
    service.shutdown()
    assert service.cleanup["all_owned_processes_terminated"]


def test_hung_worker_cancel_has_bounded_grace_and_next_job_succeeds(services, tmp_path):
    service = services(env={"CU_FAKE_PROCESS": "1", "CU_FAKE_FAULT": "stall@0",
                            "CU_CANCEL_GRACE_SECONDS": "0.3", "CU_STALL_SECONDS": "30"})
    media = service.add(inputs(tmp_path / "input", 1))[0]
    job = service.job([media["id"]])
    service.wait_job(job["id"], lambda j: j["items"][0]["state"] == "running")
    start = time.monotonic()
    service.post(f'/api/jobs/{job["id"]}/cancel')
    cancelled = service.wait_job(job["id"], timeout=15)
    assert cancelled["state"] == "cancelled"
    assert time.monotonic() - start < 15
    assert_outputs(service.wait_job(service.job([media["id"]])["id"]))


def test_watchdog_fails_hung_item_and_advances_queue(services, tmp_path):
    service = services(env={"CU_FAKE_PROCESS": "1", "CU_FAKE_FAULT": "stall@0",
                            "CU_STALL_SECONDS": "0.5", "CU_DEADLINE_SECONDS": "10"})
    media = service.add(inputs(tmp_path / "input", 1))[0]
    job = service.wait_job(service.job([media["id"]] * 2)["id"], timeout=30)
    assert [i["state"] for i in job["items"]] == ["failed", "done"]
    assert "stopped making progress" in job["items"][0]["error"]["text"]
