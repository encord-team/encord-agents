If you just want to install `encord-agents` in your current environment, you can run:

```shell
python -m pip install encord-agents
```

Note that we also optionally include additional dependencies used for working with Visual files: e.g: Images, Videos, Image Groups / Sequences. These can be used by

```shell
python -m pip install encord-agents[vision]
```

!!! info
    We recommend this for the majority of use cases as we explicitly build our methods to make working with Visual files as easy and as fast as possible. We offer it as an optional dependency to support serverless use cases where you wish to avoid bundle size or are making Agents that don't interact with the visual data in each task e.g: Working purely with label data / priorities, text / pdf files or Audio files.

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

The dependencies for `encord-agents` are kept lightweight, with the only relatively large dependencies being `numpy` with `opencv-python-headless` included in `encord-agents[vision]` also. To see the full list of dependencies, go [here](https://github.com/encord-team/encord-agents/blob/main/pyproject.toml){ target="\_blank", rel="noopener noreferrer" }.
