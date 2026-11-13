import json
import zipfile

from support_bundle import create_bundle, sanitize


def test_redacts_structured_secrets_paths_and_identifiers():
    path = 'Z:' + chr(92) + 'private' + chr(92) + 'client.png'
    source = {'token': 'keep-out', 'model_dir': path, 'user': 'person',
              'msg': 'File "' + path + '" failed; Bearer secret-value',
              'nested': {'endpoint': 'http://example.invalid/run?token=keep-out'}}
    result = json.dumps(sanitize(source))
    for private in ('keep-out', path, 'person', 'secret-value', 'example.invalid'):
        assert private not in result


def test_bundle_contains_only_sanitized_text_not_images_or_links(tmp_path):
    state = tmp_path / 'state'
    state.mkdir()
    (state / 'host.log').write_text('Bearer dont-share\n')
    (state / 'config.json').write_text(json.dumps({'token': 'dont-share', 'models_dir': str(tmp_path)}))
    (state / 'image.png').write_bytes(b'private-image')
    destination = tmp_path / 'support.zip'
    result = create_bundle(state, destination)
    assert result['files'] == 2
    with zipfile.ZipFile(destination) as archive:
        contents = b''.join(archive.read(name) for name in archive.namelist())
        assert b'dont-share' not in contents
        assert b'private-image' not in contents
        assert b'image.png' not in contents
        assert str(tmp_path).encode() not in contents


def test_rejects_existing_destination_and_never_truncates_it(tmp_path):
    target = tmp_path / 'already.zip'
    target.write_bytes(b'existing')
    import pytest
    with pytest.raises(FileExistsError):
        create_bundle(tmp_path, target)
    assert target.read_bytes() == b'existing'


def test_pretty_json_and_raw_assignments_are_scrubbed(tmp_path):
    (tmp_path / 'config.json').write_text(json.dumps({'token': 'keep-private'}, indent=2))
    (tmp_path / 'host.log').write_text('api_key=keep-private\npassword: keep-private\n')
    target = tmp_path / 'support.zip'
    create_bundle(tmp_path, target)
    with zipfile.ZipFile(target) as archive:
        assert b'keep-private' not in b''.join(archive.read(name) for name in archive.namelist())
