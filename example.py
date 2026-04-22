# -*- coding: utf-8 -*-
"""
@File    : example.py
@Time    : 2024/03/22 00:12:15
@Author  : Roney D. Silva e Equipe EFO-S

Descrição:
    Exemplo de uso da classe RotTableComm para controle da mesa inercial
    com dois eixos (Azimuth e Tilt) via Modbus TCP.

Compatibilidade:
    Python 3.12.3, pymodbus 3.7.4
"""

from rotatorytable import RotTableWrapper
from time import sleep

# =========================================================
# CONFIGURAÇÃO DE AMBIENTE
# =========================================================

SERVER_PROD = "192.168.1.1"      # Mesa real
MODBUS_PORT_PROD = 502                # Porta padrão Modbus TCP

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

rot = RotTableWrapper(host=SERVER_PROD, port=MODBUS_PORT_PROD)

# =========================================================
# 1. HABILITAR SISTEMA
# =========================================================

print("Conectando..")
rot.connect()
sleep(1) # Aguarda o sistema ser habilitado

# =========================================================
# 2. TESTE DE POSICIONAMENTO ABSOLUTO
# =========================================================

print("Teste de posicionamento (Yaw + Roll)...")

print("Move yaw para 45 graus")
rot.move_yaw(45)
sleep(5) 
# Aguarda o movimento ser concluído (ajuste conforme necessário)
# Seria ideal implementar uma função de espera baseada no status do movimento, em vez de usar sleep fixo.
# Exemplo: aguardar até que o movimento seja concluído verificando o status do eixo.
# Enquanto isso, o sleep é utilizado aqui para simplificar. Então, deve-se, com base na velocidade de posicionamento, 
# ajustar o tempo de espera para garantir que o movimento seja concluído antes de enviar o próximo comando.

print("Move roll para 30 graus")
rot.move_roll(30)
sleep(5)

print("Move yaw e roll para 0 graus")
rot.move_yaw(0)
rot.move_roll(0)
sleep(5)

# =========================================================
# 3. TESTE DE JOG (VELOCIDADE)
# =========================================================

print("Jog yaw com velocidade 20 °/s")
rot.jog_yaw(20)
sleep(5)

print("Para o jog yaw")
rot.stop_yaw()
sleep(5)

print("Jog roll com velocidade 15 °/s no sentido negativo")
rot.jog_roll(-15) # Jog no eixo Roll com velocidade de -15 graus/s (sentido contrário)
sleep(5)

print("Para o jog Roll")
rot.stop_roll()
sleep(5)

print("Jog yaw com velocidade 30 °/s no sentido negativo")
rot.jog_yaw(-30)
sleep(5)

print("Jog roll com velocidade 20 °/s")
rot.jog_roll(20)
sleep(5)
rot.stop_all()
sleep(5)

# =========================================================
# 4. TESTE COMBINADO (DOIS EIXOS)
# =========================================================

print("Teste Jog e Pos simultâneos (Yaw e Roll)...")
rot.jog_all(10)
sleep(5)

rot.stop_all()
sleep(5)

print("Jog em ambos eixos com velocidade 90 °/s")
rot.jog_all(90.0)
sleep(5)

print("Para ambos eixos")
rot.stop_all()
sleep(5)

# ==============================================================
# 5. HOMING MANUAL - retorno "para casa" ao zero mecânico lógico 
# ==============================================================

print("Retorno ao zero mecânico lógico...")

sleep(5)

rot.move_all(0) # ambos eixos para 0 graus
sleep(5)

print("Teste finalizado com sucesso.")