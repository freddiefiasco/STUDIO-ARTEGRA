# Tips

Practical advice for getting good results from Artegra Enhancer (Beta). The installation itself is in the [installation guide](../INSTALL.md).

## Redux or Bolt

| | <img src="assets/mode-redux.svg" width="20" height="20" alt="Redux mark"> Redux | <img src="assets/mode-bolt.svg" width="20" height="20" alt="Bolt mark"> Bolt |
| --- | --- | --- |
| Use it for | Finals | Drafts and quick checks |
| Scale | 2×, 4×, 6×, 8× | 2× |
| Look | Light to Extreme, or your own Detail settings | Light, Default |
| Image size | Up to 80 MP in | Up to about 9 MP |

Bolt runs in about half the time of Redux. On an RTX 5090 with the models already loaded, a 768 × 768 pixel crop at 2× took about 3 minutes in Redux and about 1.5 minutes in Bolt. Bolt's results look slightly different, so make finals in Redux.

When you choose something Bolt cannot do (a Look past Default, 4× or more, or your own Detail settings), the Mode switches to Redux and a notice says why.

## Draft in Bolt, finish in Redux

1. Queue the render in Bolt at 2× with the Look you want to try.
2. Check the result at 100 % (press **1**) and with **Before** and **After** (press **B**).
3. If the Look suits the image, choose **Upscale again in Redux** under the result. It queues the same image with the same settings in Redux.

A Bolt result is saved as `name_cu2x_bolt.png`, so drafts and finals never overwrite each other.

## Looks

| Look | What it does |
| --- | --- |
| Light | Adds fine detail; each plant keeps its species. |
| Default | New detail; shapes and layout stay as they are. |
| Strong | Crisper materials; planting may be redrawn. |
| Heavy | More new detail; planting is often redrawn. |
| Extreme | The most new detail; check planting and fine shapes. |

Start with Default. Move up a step only if surfaces still look soft, and check trees, people and small shapes at 100 % each time. **Detail** lets you set the three values behind a Look yourself (Creativity, Resemblance and Restoration); that is Redux only. If you add an extra description, describe materials, for example "polished concrete, oak floor", rather than objects: naming objects can make new ones appear.

## Scales

2× doubles each side in one pass. 4× works in two passes, and 6× and 8× in three. Every pass adds invented detail and time, so:

- try 2× first and look at it at 100 % before you queue a larger scale;
- read the line beside **Scale**: it gives the result's megapixels and the size it prints at, for example "6 MP, A3 at 181 ppi";
- for a large print, choose the smallest scale that reaches the print size you need.

## Protect

**Protect** keeps chosen things as they are while the rest of the image gets new detail. By default it covers people, furniture and objects, vehicles, and windows and glass. You can add architecture (walls, roofs, floors, doors and stairs). The protected areas can be previewed on the picture (press **M**) before you start.

## Graphics memory

Leave **Settings → Graphics memory** on **Auto**. On cards with 24 GB or less, Auto turns on **Save GPU memory**, which processes one tile at a time and loads models through system memory. It uses less graphics memory and can take longer; its pixels can differ slightly from the original settings.

If an image runs out of graphics memory, the app offers **Try again with Save GPU memory**. It asks first, because the setting then stays on for later images. You can turn it off again in Settings.

Close other programs that use the graphics card (3D apps, games, other AI tools) before a long batch.

<!-- release-draft: engines. Kept, changed or removed by the release step from the proof record. -->

## Very large outputs

- Sizes the Classic engine cannot make on your computer run on the Large-image engine. Its plan gives the estimated time, the free disk space and the memory class before the image starts.
- Queue your first Large-image image when the computer can be left to work. Unless your kind of processor was measured before this release, that image waits while the app measures the processor: about 22 to 25 minutes on our test PC's processor, and longer on a slower one.
- A Large-image upscale can restart the image engine between passes to give back the memory the last pass held. Each restart is in the estimated time.
- Keep the work drive's free space above what the plan asks for: at 8× of a 3500 × 2188 render, about 185 GB.
- The viewer never loads the whole result. It shows a reduced copy, and when you zoom in far enough it loads only the part you look at, at full detail.

<!-- /release-draft -->

## Two graphics cards

- **Bolt:** with two identical RTX 5090 desktop cards and the original memory settings, a single Bolt image is shared by both cards and finishes sooner. A batch of several Bolt images runs one image per card. On any other pair of cards, each Bolt image uses one card.
- **Redux:** one image can be shared across two cards, as in the alphas. That was proven on two RTX 5090 cards only.
- The finish time takes the cards into account. It is meant to be on the safe side: in the release tests, every image finished before the time shown.
- Two cards do not add their memory together for one image.

## Batches

- One set of settings applies to all waiting images. A change made during a batch reaches every image still waiting.
- **Stop after current** finishes the images in progress, then moves the waiting ones to **Stopped**, where you can queue them again.
- **Clear** removes finished images from the list. Their files stay in the output folder.
- **Use these settings** on a result loads the settings that result was made with.

## Where files go

- Results are saved in **Pictures → Artegra Enhancer**. Choose another folder in **Settings → Save enhanced images to**, or in **Output** on the right of the workspace, which also sets the format (PNG 8-bit, PNG 16-bit, TIFF 16-bit or JPEG).
- Names follow the original: `name_cu2x.png` for Redux at 2×, `name_cu4x.png` at 4×, and `name_cu2x_bolt.png` for Bolt. If a name is taken, `_2`, `_3` and so on is added.
- Each result has a .json file beside it with the settings used. It also holds the full paths of the original and the result, which usually include your Windows user name. Remove the .json files before you send a folder to anyone.
- Results from the alphas named `_fast` are still recognised as Bolt results.

## Keep the enhancement files on another drive

The models and the image engine take about 21 GiB. Choose their drive on the **Installation location** page of setup: a local SSD with room to spare is best. A network drive works, but installs, repairs and uninstalls take longer.

To move them later, run the installer again and choose the new location. Setup downloads the files to the new place and leaves the old copy where it was; delete the old folder yourself afterwards.

## Keyboard shortcuts

| Keys | Action |
| --- | --- |
| Ctrl+O | Add images |
| Ctrl+Enter | Start upscaling |
| Delete | Remove the selected waiting image |
| Ctrl+Z | Put back a removed image |
| B | Switch between Before and After |
| S | Split the picture |
| Y | Before and After side by side |
| L | Show or hide the loupe |
| Hold Space | Show the original |
| + or − | Zoom in or out |
| 0 or 1 | Fit, or 100 % |
| M | Show or hide the protected areas |
| Ctrl+. | Stop after current |
| Ctrl+Shift+. | Stop this image |
| R | Review the results of the last batch |
| Esc | Close a dialog, or ask to cancel the running batch |

**Shortcuts** in the header lists the ones that apply to the window as it is.
