# -*- coding: utf-8 -*-
"""
@File    : example.py
@Time    : 2024/03/22 00:12:15
@Author  : Roney D. Silva e Equipe EFO-S

Descrição:
    Exemplo de uso da classe RotTableComm para controle da mesa inercial
    Infax com dois eixos (Azimuth e Tilt) via Modbus TCP.

Compatibilidade:
    Python 3.12.3, pymodbus 3.7.4
"""

from rotatorytable import RotTableWrapper
from time import sleep

# =========================================================
# CONFIGURAÇÃO DE AMBIENTE
# =========================================================

SERVER_PROD = "192.168.1.1"      # Mesa real Infax
MODBUS_PORT = 502                # Porta padrão Modbus TCP

SERVER_TEST = "127.0.0.1"        # Simulador local. Lembre-se de iniciar o simulador antes de executar este script.
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
sleep(1) # Aguarda o sistema ser habilitado

# =========================================================
# 2. TESTE DE POSICIONAMENTO ABSOLUTO
# =========================================================

print("Teste de posicionamento (Azimuth + Tilt)...")

rt.posazi(45)
sleep(5) 
# Aguarda o movimento ser concluído (ajuste conforme necessário)
# Seria ideal implementar uma função de espera baseada no status do movimento, em vez de usar sleep fixo.
# Exemplo: aguardar até que o movimento seja concluído verificando o status do eixo.
# Enquanto isso, o sleep é utilizado aqui para simplificar. Então, deve-se, com base na velocidade de posicionamento, 
# ajustar o tempo de espera para garantir que o movimento seja concluído antes de enviar o próximo comando.


rt.postilt(30)
sleep(5)

rt.posazi(0)
rt.postilt(0)
sleep(5)

# =========================================================
# 3. TESTE DE JOG (VELOCIDADE)
# =========================================================

print("Teste Jog Azimuth +...")

rt.jogazi(20) # Jog no eixo Azimuth com velocidade de 20 graus/s
sleep(5)

rt.stop() # Para interromper o movimento de jog
sleep(5)

print("Teste Jog Tilt -...")

rt.jogtilt(-15) # Jog no eixo Tilt com velocidade de -15 graus/s (sentido contrário)
sleep(5)

rt.stop() # Para ambos eixos (v=0)

# =========================================================
# 4. TESTE COMBINADO (DOIS EIXOS)
# =========================================================

print("Teste Jog e Pos simultâneos (Azimuth + Tilt)...")

rt.jog(10) # ambos eixos com velocidade de 10 graus/s
sleep(5)

rt.stop()

rt.pos(90.0) # ambos eixos para 90 graus
sleep(5)


# ==============================================================
# 5. HOMING MANUAL - retorno "para casa" ao zero mecânico lógico 
# ==============================================================

print("Retorno ao zero mecânico lógico...")

sleep(5)

rt.pos(0) # ambos eixos para 0 graus
sleep(5)

print("Teste finalizado com sucesso.")