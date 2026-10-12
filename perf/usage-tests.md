# Usage Tests

Results gathered from running the tests in the [tests](../tests/) directory. These results are very arbitrary and should not be taken as a definitive measure of performance. They are meant to give a rough idea of how the system behaves under different conditions.

## Computer Specs

```bash
$ neofetch --off
OS: Ubuntu 23.10 x86_64
Host: Victus by HP Laptop 16-e0xxx
Kernel: 6.5.0-28-generic
Shell: zsh 5.9
DE: GNOME 45.2
Terminal: gnome-terminal
CPU: AMD Ryzen 7 5800H with Radeon Graphics (16) @ 4.463GHz
GPU: AMD ATI Radeon Vega Series / Radeon Vega Mobile Series
GPU: NVIDIA GeForce RTX 3050 Ti Mobile
Memory: 15313MiB
```

*Note:* Irrelevant information has been removed from the output.

## Results

*Python version: 3.11.8*

### test_streambase:
- no demand:
``CPU: 14-16% Memory: 39.2 MB``
- demand:
``CPU: 15-19% Memory: 39.5 MB``

### test_stream:
- no demand:
``CPU: 14-16% Memory: 39.7 MB``
- demand:
``CPU: 14-17% Memory: 41.7 MB``

### test_full_od:
  - initial no demand:
  ``CPU: 0% Memory: 37 MB``
  - no demand:
  ``CPU: 0% Memory: 39.9 MB``
  - demand:
  ``CPU: 15-18% Memory: 41 MB``

### test_fast_od:
  - initial no demand:
  ``CPU: 0% Memory: 37.2 MB``
  - no demand:
  ``CPU: 0-0.1% Memory: 41.1 MB``
  - demand:
  ``CPU: 15-18% Memory: 41.1 MB``
