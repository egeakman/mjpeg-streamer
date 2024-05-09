# PY-SPY Tests

Performance results gathered using py-spy. [Test scripts](../tests/) were run with the following command:

```bash
py-spy top -- python tests/<test_script>.py
```

## Results

*Python version: 3.11.8*

### test_streambase:
- no demand:
``GIL: 0% Active: 5-15% Threads: 2``
- demand:
``GIL: 0% Active: 5-15% Threads: 2``

### test_stream:
- no demand:
``GIL: 0% Active: 0-4% Threads: 2``
- demand:
``GIL: 0-2% Active: 3-10% Threads: 2``

### test_full_od:
  - initial no demand:
  ``GIL: 0% Active: 0-1% Threads: 2``
  - no demand:
  ``GIL: 0% Active: 0% Threads: 2``
  - demand:
  ``GIL: 0-2% Active: 2-10% Threads: 2``

### test_fast_od:
  - initial no demand:
  ``GIL: 0% Active: 0-1% Threads: 2``
  - no demand:
  ``GIL: 0% Active: 0-1% Threads: 2``
  - demand:
  ``GIL: 0-2% Active: 2-10% Threads: 2``
