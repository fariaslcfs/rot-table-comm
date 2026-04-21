# -*- coding: utf-8 -*-
"""
@File    : example.py
@Time    : 2024/03/22 00:12:15
@Author  : Roney D. Silva e Equipe EFO-S

Descrição:
    Exemplo de uso da classe RotTableComm para controle da mesa inercial
    Infax com dois eixos (Azimuth e Tilt) via Modbus TCP.

Compatibilidade:
    Python 3.9+
"""

from rotatorytable import RotTableWrapper
from time import sleep

# =========================================================
# CONFIGURAÇÃO DE AMBIENTE
# =========================================================

SERVER_PROD = "192.168.1.1"      # Mesa real Infax
MODBUS_PORT = 502                # Porta padrão Modbus TCP

SERVER_TEST = "127.0.0.1"        # Simulador local
MODBUS_PORT_TEST = 5020          # Evita conflito com porta 502 (well-known)

# =========================================================
# OBSERVAÇÃO IMPORTANTE (SIMULADOR)
# =========================================================
"""
Para execução do simulador sem interação manual, é necessário o arquivo:
    mesa_config.json

Este arquivo é o mesmo utilizado pelo projeto ScriptMesaPython:
    https://github.com/IEAv-EFO/ScriptMesaPython.git
"""

# =========================================================
# INSTANCIAÇÃO DO CONTROLADOR
# =========================================================

rt = RotTableWrapper(host=SERVER_TEST, port=MODBUS_PORT_TEST)

# =========================================================
# 1. HABILITAR SISTEMA
# =========================================================

print("Habilitando controlador da mesa...")
rt.enable()
sleep(0.2)

# =========================================================
# 2. TESTE DE POSICIONAMENTO ABSOLUTO
# =========================================================

print("Teste de posicionamento (Azimuth + Tilt)...")

rt.pos("azimuth", 45)
sleep(2)

rt.pos("tilt", 30)
sleep(2)

rt.pos("azimuth", 0)
rt.pos("tilt", 0)
sleep(2)

# =========================================================
# 3. TESTE DE JOG (VELOCIDADE)
# =========================================================

print("Teste Jog Azimuth +...")

rt.jog("azimuth", 20)
sleep(3)

rt.stop()
sleep(1)

print("Teste Jog Tilt -...")

rt.jog("tilt", -15)
sleep(3)

rt.stop()

# =========================================================
# 4. TESTE COMBINADO (DOIS EIXOS)
# =========================================================

print("Teste Jog simultâneo (Azimuth + Tilt)...")

rt.jog("both", 10)
sleep(4)

rt.stop()

# =========================================================
# 5. HOMING MANUAL
# =========================================================

print("Retorno ao zero mecânico lógico...")

sleep(5)

rt.pos("azimuth", 0)
sleep(3)
rt.pos("tilt", 0)
sleep(3)
print("Teste finalizado com sucesso.")