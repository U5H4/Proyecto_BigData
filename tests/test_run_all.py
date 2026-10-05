"""Pruebas del orquestador `src/run_all.py`.

El fallo que estas pruebas protegen es silencioso: si la seleccion de etapas se
rompe, el pipeline sigue terminando con codigo 0 y solo cambia *cuanto* tarda
o *que* imprime. Un `tests` que se cuela en la ejecucion por defecto duplica el
tiempo del pipeline, y un `--solo` mal filtrado se come una etapa sin avisar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import run_all  # noqa: E402


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def main_con_captura(monkeypatch_module):
    """Ejecuta `main()` con argv fijo y devuelve las claves que se correrian.

    `ejecutar` queda interceptado a proposito: sin esto, `--solo tests` lanza
    pytest desde dentro de pytest, y cada proceso anidado corre la suite
    otra vez -- una recursion que cuelga la maquina.
    """
    def _correr(argv: list[str]) -> list[str]:
        capturadas: list[str] = []
        monkeypatch_module.setattr(
            run_all, "ejecutar", lambda claves: capturadas.append(list(claves)) or 0
        )
        monkeypatch_module.setattr(sys, "argv", ["run_all.py", *argv])
        assert run_all.main() == 0
        return capturadas[0]
    return _correr


# --------------------------------------------------------------------------
# Seleccion de etapas
# --------------------------------------------------------------------------
def test_etapa_de_tests_no_corre_por_defecto(main_con_captura):
    """`pytest` duplica el tiempo del pipeline y no cambia ningun artefacto.

    La etapa es opcional (`obligatoria=False`) y tanto el docstring como el
    README prometen que solo entra con `--con-tests`.
    """
    claves = main_con_captura([])
    assert "tests" not in claves
    assert claves == ["generar", "etl", "integracion", "analisis", "graficos"]


def test_con_tests_agrega_pytest_al_final(main_con_captura):
    claves = main_con_captura(["--con-tests"])
    assert claves[-1] == "tests"
    assert claves[:5] == ["generar", "etl", "integracion", "analisis", "graficos"]


def test_sin_generar_conserva_el_resto(main_con_captura):
    claves = main_con_captura(["--sin-generar"])
    assert "generar" not in claves
    assert claves == ["etl", "integracion", "analisis", "graficos"]


def test_solo_respeta_el_orden_del_pipeline(main_con_captura):
    """El orden de los argumentos no manda: las etapas dependen entre si."""
    assert main_con_captura(["--solo", "graficos", "analisis"]) == ["analisis", "graficos"]
    assert main_con_captura(["--solo", "analisis"]) == ["analisis"]


def test_solo_admite_etapas_opcionales(main_con_captura):
    assert main_con_captura(["--solo", "tests"]) == ["tests"]
    assert main_con_captura(["--solo", "tests", "etl"]) == ["etl", "tests"]


def test_etapa_desconocida_es_error_de_uso(monkeypatch_module):
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    try:
        mp.setattr(sys, "argv", ["run_all.py", "--solo", "bogus"])
        assert run_all.main() == 2, "una etapa inexistente debe salir con codigo 2, no 0"
    finally:
        mp.undo()


# --------------------------------------------------------------------------
# Contrato de las etapas declaradas
# --------------------------------------------------------------------------
def test_todas_las_etapas_excepto_tests_son_obligatorias():
    opcionales = [e.clave for e in run_all.ETAPAS if not e.obligatoria]
    assert opcionales == ["tests"]


def test_etapa_tests_propaga_el_codigo_de_salida_de_pytest():
    """Si pytest falla, la etapa debe devolver su codigo, no tragarselo.

    `ejecutar()` marca FALLO cuando la etapa devuelve un int distinto de 0;
    si `etapa_tests` devolviera siempre None, un suite en rojo pasaria
    desapercibido y el pipeline reportaria exito.
    """
    import subprocess

    class _Falso:
        returncode = 1

    original = subprocess.run
    try:
        subprocess.run = lambda *a, **k: _Falso()  # type: ignore[assignment]
        assert run_all.etapa_tests() == 1
        _Falso.returncode = 0
        assert run_all.etapa_tests() == 0
    finally:
        subprocess.run = original  # type: ignore[assignment]
