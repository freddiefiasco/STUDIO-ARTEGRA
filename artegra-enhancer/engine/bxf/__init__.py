"""The banded exact finish (BXF) of the Large-image engine: its numeric machinery (engine design ENGINE-DESIGN.md sections 2.4
and 2.5). Pure numpy at import; scipy and torch are imported inside the functions that need them, so importing this package
changes no global state (G0d).

  work        scratch planes: memory-mapped files under the finish's work folder (file-backed, so commit-free; G6)
  local       the band executor of local (E1) ops: the same call on a band plus a halo of real rows, the core rows kept
  selection   E5: exact streamed order statistics and numpy's own percentile / median arithmetic over planes
  uniform     E2: scipy's uniform_filter as uniform_filter1d along axis 0 on full-height strips, then axis 1 on row bands
  pooling     E3: the finish's reshape-mean pooled grids on bands that start on multiples of 288 rows; E4 whole-call zoom
  components  E6: label on mapped planes, streamed bincount, find_objects windows, keep tables, per-component statistics
  pool        a pool of CPU processes for registered numpy/scipy band ops (children load this package by path)
  ops         the band ops a pool child may run (numpy and scipy only; never torch)
  g1          the G1 classification table reader: an op runs banded only where G1 measured 0 differing values

Inside the worker the node pack loads this code by path as cu_banded_engine.bxf.* (node_pack/claude_banded _engine()), so every
module here uses relative imports only."""
