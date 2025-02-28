If you just want to install `encord-agents` in your current environment, you can run:

```shell
python -m pip install encord-agents
```

!!! warning
    This Project requires `python >= 3.10`. If you do not have Python 3.10, we recommend using, e.g., [`pyenv`](https://github.com/pyenv/pyenv){ target="\_blank", rel="noopener noreferrer" } to manage your Python versions.

---

## Using an Isolated Environment (Recommended)

We recommend installing the Encord agents library in an isolated environment. There are several options available. 

### Venv

1. Create a new virtual environment. In this example, we name it `agents-venv` but you can choose any name you see fit.

```shell
python -m venv agents-venv
```

2. Next, activate your virtual environment. This ensures that any modules you install remain isolated and that all previously installed modules in the environment are available for use in Python.

```shell
source agents-venv/bin/activate
```

3. Once activated, the environment name is displayed before the cursor in your terminal.

```shell title="example"
(agents-venv) $
```

4. Install the `encord-agents` library.

```shell
python -m pip install encord-agents
```

### Poetry

If you already have a Poetry project, you can add `encord-agents` to that project:

```shell
poetry add encord-agents
```

### Conda

1. Create a conda environment.

```
conda create -n agents python>=3.10
```

2. We suggest activating your conda environment.

```shell
conda activate agents
```

3. Once activated, the environment name is displayed before the cursor in your terminal.

```shell title="example"
(agents) $
```

4. Install the `encord-agents` library.

```shell
python -m pip install encord-agents
```

## Dependencies

The dependencies for `encord-agents` are kept lightweight, with the only relatively large dependencies being `opencv-python` and `numpy`. To see the full list of dependencies, go [here](https://github.com/encord-team/encord-agents/blob/main/pyproject.toml){ target="\_blank", rel="noopener noreferrer" }.
