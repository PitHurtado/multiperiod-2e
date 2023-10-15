"""Entrypoint for nox"""
import nox_poetry as nox


@nox.session(reuse_venv=True, python=["3.9"])
def tests(session):
    """Run all tests"""
    session.run("poetry", "install", "--no-dev", external=True)
    cmd = ["poetry", "run", "pytest"]
    if session.posargs:
        cmd.extend(session.posargs)
    session.run(*cmd, external=True)
