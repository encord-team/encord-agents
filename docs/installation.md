If you just want to install `encord-agents` in your current environment, you can run:

```shell
python -m pip install git+https://github.com/encord-team/encord-agents
```

> ℹ️ This project requires `python >= 3.10`. If you do not have python 3.10, we recommend using, e.g., [`pyenv`](https://github.com/pyenv/pyenv) to manage your python versions.

---

## In an isolated environment (recommended)

There are multiple ways of maintaining python environments.
Below,

### Venv

To avoid installing `encord-agents` with your global python installation, you can create a virtual environment with `venv` and install it there.

First create a new virtual environment. In this example, we name it `agents-venv` but you can choose whatever.

```shell
python -m venv agents-venv
```

Once it's created, you can activate it.
Activating it will make the modules that you installed in that virtual environment available in python:

```shell
source agents-venv/bin/activate
```

Now you should see the environment before the cursor in your terminal.

```shell title="example"
(agents-venv) $
```

Now install `encord-agents` as above:

```shell
python -m pip install git+https://github.com/encord-team/encord-agents
```

### Poetry

If you already have a poetry project, you can also add `encord-agents` to that project:

```shell
poetry add git+https://github.com/encord-team/encord-agents
```

### Conda

If you haven't already, create a conda environment:

```
conda create -n agents python>=3.10
```

For conda, we suggest activating your conda environment:

```shell
conda activate agents
```

Now you should see the environment before the cursor in your terminal.

```shell title="example"
(agents) $
```

Then, install `encord-agents` within the environment:

```shell
python -m pip install git+https://github.com/encord-team/encord-agents
```

## Dependencies

The dependencies of `encord-agents` are choosen to be lite.
The only heavy dependencies that are somewhat heavy are `opencv-python` and `numpy`.
To see the full list of dependencies, you can have a look [here](https://github.com/encord-team/encord-agents/blob/main/pyproject.toml).
