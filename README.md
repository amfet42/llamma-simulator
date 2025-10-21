# Curve LLAMMA Simulator

## Installation

### Locally using uv

```
pip install uv
uv venv
uv sync
```

## Running simulations

### Import data

1) Add pair to simulator/settings.py

```
python manage.py import_data {pair_name} (i.e. BTCUSDT)
```

2) Change parameters in python manage.py for `calculate` command

3) Run simulations
```
python manage.py calculate
```
