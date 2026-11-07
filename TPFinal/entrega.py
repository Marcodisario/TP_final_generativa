"""Punto de entrada que usa el kit de evaluación de la cátedra."""

from buscador_rag import construir_buscador


def construir_agente():
    """Carga el modelo local para evaluar prompts; requiere dependencias de prompt_gpu."""
    from prompt_gpu.agente import construir_agente_local
    return construir_agente_local()


__all__ = ["construir_buscador", "construir_agente"]

