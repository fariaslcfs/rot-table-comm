##### SCRIPT FUNCIONAL PARA TESTES #####

# -*- coding: utf-8 -*-
"""
MESA INERCIAL 2 EIXOS - VERSÃO INDUSTRIAL HARDENED (COMPLETA)
Python 3.12 | Flask + pymodbus | Logging profissional + Config JSON persistente
Locks de thread + Retries Modbus + stop_event + Shutdown gracioso
Porta web: 8080 | Modbus: 192.168.1.1:502
"""
import time
import os
import re
import json
import logging
import threading
import signal
import sys
from datetime import datetime
from io import BytesIO
from logging.handlers import RotatingFileHandler
from threading import Lock, Event
from flask import Flask, request, jsonify, Response, send_file, make_response, render_template
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException
from tkinter import Tk, filedialog

# ====================== CONFIGURAÇÃO ======================
SERVER = "127.0.0.1"
MODBUS_PORT = 5020
WEB_PORT = 8080
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_DADOS = os.path.join(SCRIPT_DIR, "dadosMesa.txt")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "mesa_config.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "mesa_control.log")
RECONNECT_INTERVAL = 5
MAX_RETRIES = 3
# ========================================================

# ====================== LOGGING ======================
logger = logging.getLogger("mesa_inercial")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(threadName)-12s | %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)
fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
fh.setFormatter(formatter)
logger.addHandler(fh)

# ====================== GLOBALS + LOCKS ======================
modbus_lock = Lock()
data_lock = Lock()
stop_event = Event() # substitui stop_flag global
rec = False
fp = None
# Parâmetros de movimento (persistidos)
VPosAzi = APosAzi = MaxVelAzi = MaxAccAzi = 0.0
VPosTilt = APosTilt = MaxVelTilt = MaxAccTilt = 0.0
client = ModbusTcpClient(SERVER, port=MODBUS_PORT, timeout=2.0)
last_connection_status = False
mark_counter = 0
mark_total = 0
stop_event = threading.Event()
stop_azi = threading.Event()
stop_tilt = threading.Event()

# ====================== MAPA DE REGISTRADORES ======================
REG_MAP = {
    # -------- AZIMUTE --------
    "velPosAzimute": {"alias": "VPA", "type": "HR", "addr": 72, "scale": 100.0},
    "accPosAzimute": {"alias": "APA", "type": "HR", "addr": 74, "scale": 100.0},
    "maxVelAzimute": {"alias": "MVA", "type": "HR", "addr": 90, "scale": 100.0},
    "maxAccAzimute": {"alias": "MAA", "type": "HR", "addr": 92, "scale": 100.0},

    # -------- TILT --------
    "velPosTilt": {"alias": "VPT", "type": "HR", "addr": 62, "scale": 100.0},
    "accPosTilt": {"alias": "APT", "type": "HR", "addr": 64, "scale": 100.0},
    "maxVelTilt": {"alias": "MVT", "type": "HR", "addr": 80, "scale": 100.0},
    "maxAccTilt": {"alias": "MAT", "type": "HR", "addr": 82, "scale": 100.0},
}

ALIAS_MAP = {v["alias"]: k for k, v in REG_MAP.items()}


# ====================== CONFIG PERSISTENTE ======================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ====================== FLASK ======================
# Inicializa o Flask com os caminhos ajustados
app = Flask(__name__,
            template_folder=resource_path('templates'),
            static_folder=resource_path('static')
)

def load_config_file():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_config():
    defaults = {
        "velPosAzimute": 30.0,
        "accPosAzimute": 100.0,
        "maxVelAzimute": 500.0,
        "maxAccAzimute": 100.0,

        "velPosTilt": 30.0,
        "accPosTilt": 100.0,
        "maxVelTilt": 200.0,
        "maxAccTilt": 100.0,

        "posIniAzimute": 0.0,
        "posIniTilt": 0.0,
        "velIniAzimute": 0.0,
        "velIniTilt": 0.0,
        "K": 1.0,
        "DT": 0.001
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)

            # merge seguro
            merged = {**defaults, **data}

            logger.info("✅ Config carregada do JSON")
            return merged

        except Exception as e:
            logger.error(f"Erro ao ler config: {e}")

    logger.warning("⚠️ Usando defaults")
    return defaults

def apply_config(config):
    global VPosAzi, APosAzi, MaxVelAzi, MaxAccAzi
    global VPosTilt, APosTilt, MaxVelTilt, MaxAccTilt

    VPosAzi   = config["velPosAzimute"]
    APosAzi   = config["accPosAzimute"]
    MaxVelAzi = config["maxVelAzimute"]
    MaxAccAzi = config["maxAccAzimute"]

    VPosTilt   = config["velPosTilt"]
    APosTilt   = config["accPosTilt"]
    MaxVelTilt = config["maxVelTilt"]
    MaxAccTilt = config["maxAccTilt"]

    # AZI
    write_register(50, int(APosAzi * 100))
    write_register(52, int(APosAzi * 100))
    write_register(72, int(VPosAzi * 100))
    write_register(74, int(APosAzi * 100))
    write_register(76, int(APosAzi * 100))
    write_register(90, int(MaxVelAzi * 100))
    write_register(92, int(MaxAccAzi * 100))

    # TILT
    write_register(40, int(APosTilt * 100))
    write_register(42, int(APosTilt * 100))
    write_register(62, int(VPosTilt * 100))
    write_register(64, int(APosTilt * 100))
    write_register(66, int(APosTilt * 100))
    write_register(80, int(MaxVelTilt * 100))
    write_register(82, int(MaxAccTilt * 100))

    # Comando de aplicação
    write_register(20, 2)
    time.sleep(1)
    write_register(20, 0)

def save_config():

    data = {
        # ==============================
        # POSICIONAMENTO (PADRÃO UNIFICADO)
        # ==============================
        "velPosAzimute": float(VPosAzi),
        "accPosAzimute": float(APosAzi),
        "maxVelAzimute": float(MaxVelAzi),
        "maxAccAzimute": float(MaxAccAzi),

        "velPosTilt": float(VPosTilt),
        "accPosTilt": float(APosTilt),
        "maxVelTilt": float(MaxVelTilt),
        "maxAccTilt": float(MaxAccTilt),

        # ==============================
        # SIMULADOR (COM FALLBACK)
        # ==============================
        "posIniAzimute": float(globals().get("posIniAzimute", 0.0)),
        "posIniTilt": float(globals().get("posIniTilt", 0.0)),

        "velIniAzimute": float(globals().get("velIniAzimute", 0.0)),
        "velIniTilt": float(globals().get("velIniTilt", 0.0)),

        "K": float(globals().get("K", 1.0)),
        "DT": float(globals().get("DT", 0.001))
    }

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        logger.info("💾 Configurações salvas (formato unificado)")

    except Exception as e:
        logger.error(f"Falha ao salvar config: {e}")

def salvar_script_local(conteudo):
    root = Tk()
    root.withdraw()

    caminho = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Arquivos de texto", "*.txt")],
        initialfile=f"scriptComandosMesa_{datetime.now().strftime('%H-%M_%d-%m-%Y')}.txt"
    )

    if caminho:
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)

    return caminho

def check_stop():
    if stop_event.is_set():
        raise InterruptedError("Script interrompido")

def safe_write(func, *args):
    check_stop()
    return func(*args)

def executa_script_worker(script_text):

    global script_thread, mark_counter
 
    def check_stop():
        if stop_event.is_set():
            raise InterruptedError("Script interrompido")

    linhas = script_text.splitlines()
    executadas = 0
    erros = []

    write_register(40, 10000)
    write_register(42, 10000)
    write_register(50, 10000)
    write_register(52, 10000)
    write_register(22, 1)
    write_register(24, 1) 

    logger.info("Iniciando execução de script...")

    try:
        for linha_num, linha in enumerate(linhas, 1):

            check_stop()

            linha = linha.strip()

            if not linha or linha.startswith('#'):
                continue

            partes = re.split(r'\s+', linha, maxsplit=1)
            cmd = partes[0].upper()

            # =========================
            # MARK (sem parâmetro)
            # =========================
            if cmd == 'MARK':
                mark_counter += 1
                logger.info(f"MARK → ciclo {mark_counter}")
                executadas += 1
                continue

            # =========================
            # Comandos com valor
            # =========================
            if len(partes) < 2:
                erros.append(f"Linha {linha_num}: Parâmetro ausente")
                continue

            try:
                valor = float(partes[1])
            except:
                erros.append(f"Linha {linha_num}: Valor inválido")
                continue

            # =========================
            # AZPOS
            # =========================
            if cmd == 'AZPOS':

                pAzimute = valor * 1000
                if pAzimute < 0:
                    pAzimute = 360000 - abs(pAzimute)

                write_register(24, 2)
                time.sleep(0.02)
                write_register(28, 0)
                time.sleep(0.02)
                write_dword(70, int(pAzimute))
                write_register(50, int(10000))
                write_register(52, int(10000))
                # write_register(72, int(VPosAzi))
                time.sleep(0.02)
                write_register(28, 4)
                time.sleep(0.02)

                logger.info(f"AZPOS {valor}°")
                executadas += 1

            # =========================
            # AZVEL
            # ========================= 
            elif cmd == 'AZVEL':

                write_register(50, 10000)
                write_register(52, 10000)
                write_register(24, 1)
                write_register(22, 1)

                # write_register(28, 0)

                v = valor * 100.0

                if v < 0:
                    write_dword(56, int(abs(v)))
                    write_register(28, 2)
                elif v > 0:
                    write_dword(56, int(v))
                    write_register(28, 1)
                else:
                    write_register(28, 0)

                logger.info(f"AZVEL {valor:.4f}°/s")
                executadas += 1

            # =========================
            # TLPOS
            # =========================
            elif cmd == 'TLPOS':

                pTilt = valor * 1000
                if pTilt < 0:
                    pTilt = 360000 - abs(pTilt)

                write_register(22, 2)
                time.sleep(0.02)
                write_register(26, 0)
                time.sleep(0.02)
                write_dword(60, int(pTilt))
                write_register(40, 10000)
                write_register(42, 10000)
                # write_register(62, int(VPosTilt))
                time.sleep(0.02)
                write_register(26, 4)
                time.sleep(0.02)

                logger.info(f"TLPOS {valor}°")
                executadas += 1

            # =========================
            # TLVEL
            # =========================
            elif cmd == 'TLVEL':

                write_register(40, 10000)
                write_register(42, 10000)
                write_register(22, 1) # Os 2 registradores 22 e 24 devem estar juntos aqui
                write_register(24, 1)

                v = valor * 100.0

                if v < 0:
                    write_dword(46, int(abs(v)))
                    write_register(26, 2)
                elif v > 0:
                    write_dword(46, int(v))
                    write_register(26, 1)
                else:
                    write_register(26, 0)

                logger.info(f"TLVEL {valor:.4f}°/s")
                executadas += 1

            # =========================
            # WAIT (interruptível)
            # =========================
            elif cmd == 'WAIT':
                segundos = valor
                if segundos > 0:
                    logger.info(f"WAIT {segundos}s")
                    for _ in range(int(segundos * 10)):
                        check_stop()
                        time.sleep(0.1)
                    executadas += 1

            # =========================
            # NÃO IMPLEMENTADOS
            # =========================
            elif cmd in ('AZACC', 'AZVPOS', 'TLACC', 'TLVPOS'):
                logger.info(f"{cmd} {valor} → não implementado")
                executadas += 1

            else:
                erros.append(f"Linha {linha_num}: Comando desconhecido '{cmd}'")

    except InterruptedError:
        logger.warning("Script interrompido com segurança")

    except Exception as ex:
        logger.error(f"Erro inesperado: {ex}")
        erros.append(str(ex))

    finally:
        logger.info(f"Finalizado: {executadas} comandos válidos, {len(erros)} erro(s)")
        script_thread = None

def read_param(name):
    reg = REG_MAP[name]
    if reg["type"] == "HR":
        raw = read_hr(reg["addr"])
    else:
        raw = read_ir(reg["addr"])

    scaled = raw / reg["scale"]
    logger.info(f"READ_PARAM → {name:15} | raw = {raw:8} | scaled = {scaled:.3f} | scale usada = {reg['scale']}")
    return scaled

def write_param(name, value):
    reg = REG_MAP[name]

    if reg["type"] != "HR":
        raise Exception(f"{name} não é gravável")

    raw = int(value * reg["scale"])
    write_hr(reg["addr"], raw)

# ====================== MODBUS HELPERS ======================
def connect_client():
    if not client.is_socket_open():
        try:
            if not client.connect():
                raise ConnectionException("Falha na conexão Modbus")
        except Exception as e:
            logger.warning(f"Falha ao conectar Modbus: {e}")
            raise

def read_uint32(addr):
    for attempt in range(MAX_RETRIES):
        try:
            with modbus_lock:
                connect_client()
                # CORREÇÃO AQUI: usando argumentos nomeados
                rr = client.read_input_registers(address=addr, count=2)
                if rr.isError():
                    raise ModbusException(f"Erro na leitura: {rr}")
                low = rr.registers[0]
                high = rr.registers[1]
                return (high << 16) | low
        except Exception as e:
            logger.warning(f"read_uint32({addr}) tentativa {attempt+1}/{MAX_RETRIES} falhou: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.3 * (attempt + 1))
                try:
                    with modbus_lock:
                        client.close()
                        client.connect()
                except:
                    pass
    raise Exception(f"read_uint32({addr}) falhou após {MAX_RETRIES} tentativas")

def read_int32(addr):
    val = read_uint32(addr)
    if val & 0x80000000:
        val -= 0x100000000
    return val

def read_register(addr):
    """Lê um único registrador (16 bits) - usado para configurações"""
    for attempt in range(MAX_RETRIES):
        try:
            with modbus_lock:
                connect_client()
                rr = client.read_input_registers(address=addr, count=1)
                if rr.isError():
                    raise ModbusException(f"Erro na leitura: {rr}")
                return rr.registers[0]
        except Exception as e:
            logger.warning(f"read_register({addr}) tentativa {attempt+1}/{MAX_RETRIES} falhou: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.3 * (attempt + 1))
                try:
                    with modbus_lock:
                        client.close()
                        client.connect()
                except:
                    pass
    logger.error(f"Falha ao ler registrador {addr} após {MAX_RETRIES} tentativas")
    return 0  # valor seguro em caso de falha

def write_register(addr, value):
    for attempt in range(MAX_RETRIES):
        try:
            with modbus_lock:
                connect_client()
                client.write_register(address=addr, value=int(value) & 0xFFFF)
                return
        except Exception as e:
            logger.warning(f"write_register({addr}) tentativa {attempt+1}/{MAX_RETRIES} falhou: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.3 * (attempt + 1))
                try:
                    with modbus_lock:
                        client.close()
                        client.connect()
                except:
                    pass

    raise Exception(f"write_register({addr}) falhou após {MAX_RETRIES} tentativas")

def write_dword(addr, value):
    for attempt in range(MAX_RETRIES):
        try:
            with modbus_lock:
                connect_client()
                low = int(value) & 0xFFFF
                high = (int(value) >> 16) & 0xFFFF
                # CORREÇÃO AQUI
                client.write_registers(address=addr, values=[low, high])
                return
        except Exception as e:
            logger.warning(f"write_dword({addr}) tentativa {attempt+1}/{MAX_RETRIES} falhou: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.3 * (attempt + 1))
                try:
                    with modbus_lock:
                        client.close()
                        client.connect()
                except:
                    pass
    raise Exception(f"write_dword({addr}) falhou após {MAX_RETRIES} tentativas")

def read_hr(addr):
    rr = client.read_holding_registers(address=addr, count=1)
    if rr.isError():
        raise Exception(f"Erro leitura HR[{addr}]")
    return rr.registers[0]

def read_ir(addr):
    rr = client.read_input_registers(address=addr, count=1)
    if rr.isError():
        raise Exception(f"Erro leitura IR[{addr}]")
    return rr.registers[0]

def write_hr(addr, value):
    rq = client.write_register(address=addr, value=value)
    if rq.isError():
        raise Exception(f"Erro escrita HR[{addr}]")

def resolve_name(token):
    token = token.upper()

    if token in ALIAS_MAP:
        return ALIAS_MAP[token]

    if token in REG_MAP:
        return token

    return None

def is_connected():
    try:
        with modbus_lock:
            if not client.is_socket_open():
                if not client.connect():
                    return False
            rr = client.read_input_registers(address=0, count=1)
            return not rr.isError()
    except Exception:
        return False

def le_dados():
    """
    Lê posição e velocidade com leitura atômica + fator configurável.
    """
    try:
        with modbus_lock:
            connect_client()
            # Lê todos os 8 registradores de uma única vez (mais atômico)
            rr = client.read_input_registers(address=0, count=8)
            if rr.isError():
                raise ModbusException(f"Erro na leitura em bloco: {rr}")

        # Raw values (32 bits)
        pos_azi_raw = (rr.registers[1] << 16) | rr.registers[0]
        vel_azi_raw = (rr.registers[3] << 16) | rr.registers[2]
        pos_tilt_raw = (rr.registers[5] << 16) | rr.registers[4]
        vel_tilt_raw = (rr.registers[7] << 16) | rr.registers[6]

        # Converte para signed int32
        def to_int32(raw):
            if raw & 0x80000000:
                return raw - 0x100000000
            return raw

        # ====================== FATOR DE ESCALA ======================
        SCALE_FACTOR = 1000000

        pos_azi = to_int32(pos_azi_raw) / SCALE_FACTOR
        vel_azi = to_int32(vel_azi_raw) / SCALE_FACTOR
        pos_tilt = to_int32(pos_tilt_raw) / SCALE_FACTOR
        vel_tilt = to_int32(vel_tilt_raw) / SCALE_FACTOR

        logger.debug(f"Raw → Azi Pos={pos_azi_raw} Vel={vel_azi_raw} | Tilt Pos={pos_tilt_raw} Vel={vel_tilt_raw}")
        logger.debug(f"Convertido (fator {SCALE_FACTOR}) → Azi Pos={pos_azi:.4f} Vel={vel_azi:.4f} | Tilt Pos={pos_tilt:.4f} Vel={vel_tilt:.4f}")

        return [pos_azi, vel_azi, pos_tilt, vel_tilt]

    except Exception as e:
        logger.error(f"Erro ao ler dados da mesa: {e}")
        raise

def try_reconnect():
    global last_connection_status
    while True:
        time.sleep(RECONNECT_INTERVAL)
        current = is_connected()
        if current and not last_connection_status:
            logger.info("Modbus reconectado com sucesso!")
            last_connection_status = True
        elif not current and last_connection_status:
            logger.warning(f"Perda de conexão detectada. Tentando reconectar a cada {RECONNECT_INTERVAL}s...")
            last_connection_status = False
        if not current:
            try:
                with modbus_lock:
                    client.close()
                    client.connect()
            except:
                pass

def para_todos():
    stop_event.set()

    # Para ambos eixos
    write_register(26, 0)
    write_register(28, 0)

    logger.warning("PARADA GERAL acionada")


    if stop_event.is_set():
        raise InterruptedError("Script interrompido")

def shutdown_gracefully(sig=None, frame=None):
    logger.info("Shutdown solicitado. Finalizando recursos...")
    stop_event.set()
    with data_lock:
        global fp
        if fp and not fp.closed:
            try:
                fp.close()
            except:
                pass
    try:
        client.close()
    except:
        pass
    logger.info("Servidor encerrado com segurança.")
    sys.exit(0)

# ====================== ROTAS API ======================
@app.route('/api/dados', methods=['GET'])
def api_dados():
    global rec, fp
    try:
        dados = le_dados()   # [pos_azi, vel_azi, pos_tilt, vel_tilt]

        # Formatação com 4 casas decimais
        linha = f"{dados[0]:.4f}\t{dados[1]:.4f}\t{dados[2]:.4f}\t{dados[3]:.4f}\n"

        with data_lock:
            if rec and fp and not fp.closed:
                fp.write(linha)
                fp.flush()   # garante que seja escrito imediatamente

        return jsonify({
            "t": time.time(),
            "azimutePosicaoLida": round(dados[0], 4),
            "azimuteVelocidadeLida": round(dados[1], 4),
            "tiltPosicaoLida": round(dados[2], 4),
            "tiltVelocidadeLida": round(dados[3], 4),
            "conectado": True
        })

    except Exception as e:
        logger.error(f"Erro em api_dados: {e}")
        return jsonify({
            "azimutePosicaoLida": "---", 
            "azimuteVelocidadeLida": "---",
            "tiltPosicaoLida": "---", 
            "tiltVelocidadeLida": "---",
            "conectado": False, 
            "erro": "Falha na comunicação com a mesa"
        }), 503

    except Exception:
        return jsonify({
            "azimutePosicaoLida": "---", "azimuteVelocidadeLida": "---",
            "tiltPosicaoLida": "---", "tiltVelocidadeLida": "---",
            "conectado": False, "erro": "Falha na comunicação com a mesa"
        }), 503

@app.route('/api/arquivo_existe', methods=['GET'])
def api_arquivo_existe():
    existe = os.path.exists(ARQUIVO_DADOS)
    return jsonify({"existe": existe})

@app.route('/api/status_gravacao', methods=['GET'])
def api_status_gravacao():
    global rec
    return jsonify({"gravando": rec})

@app.route('/api/gravacao', methods=['POST'])
def api_gravacao():
    global rec, fp
    with data_lock:
        if rec:
            return jsonify({"status": "ok", "message": "Já está gravando"})

        try:
            os.makedirs(os.path.dirname(ARQUIVO_DADOS), exist_ok=True)

            # 🔥 MODO CORRETO: sobrescreve arquivo
            fp = open(ARQUIVO_DADOS, "w", encoding="utf-8", buffering=1)

            # 🔥 ESCREVE CABEÇALHO
            fp.write(" AZPOS   AZVEL   TLPOS   TLVEL\n")

            rec = True

            logger.info(f"✅ Gravação INICIADA → {ARQUIVO_DADOS}")
            logger.info(f"Caminho completo: {os.path.abspath(ARQUIVO_DADOS)}")

            return jsonify({
                "status": "ok",
                "message": "Gravação iniciada com sucesso",
                "path": os.path.abspath(ARQUIVO_DADOS)
            })

        except PermissionError:
            logger.error("❌ Permissão negada para escrever em dadosMesa.txt")
            return jsonify({"erro": "Sem permissão para criar/escrever no arquivo"}), 500

        except Exception as e:
            logger.error(f"❌ Erro ao abrir arquivo de gravação: {e}")
            return jsonify({"erro": str(e)}), 500

@app.route('/api/parar_gravacao', methods=['POST'])
def api_parar_gravacao():
    global rec, fp
    with data_lock:
        rec = False
        if fp and not fp.closed:
            fp.close()
            fp = None
    logger.info("Gravação parada")
    return jsonify({"status": "ok", "message": "Gravação parada com sucesso"})

@app.route('/api/parar', methods=['POST'])
def api_parar():
    data = request.get_json(silent=True) or {}
    eixo = data.get('eixo', 'ambos')

    try:
        # =========================
        # PARADA GERAL (E-STOP)
        # =========================
        if eixo == 'ambos':

            stop_event.set()
            stop_azi.set()
            stop_tilt.set()

            # parada física
            write_register(26, 0)  # tilt
            write_register(28, 0)  # azi

            # opcional (se existir)
            try:
                para_todos()
            except:
                pass

            logger.warning("PARADA GERAL (ambos) acionada")

        # =========================
        # PARADA POR EIXO
        # =========================
        else:

            if eixo == 'tilt':
                stop_tilt.set()
                write_register(26, 0)

            elif eixo == 'azi':
                stop_azi.set()
                write_register(28, 0)

            logger.warning(f"PARADA LOCAL → eixo: {eixo}")

        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Erro ao parar: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/emergencia', methods=['POST'])
def api_emergencia():
    stop_event.set()
    if not is_connected():
        return jsonify({"status": "erro", "message": "Sem conexão"}), 503
    try:
        write_dword(20, 4)
        time.sleep(1)
        write_dword(20, 0)
        time.sleep(1)
        logger.warning("EMERGÊNCIA executada")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Erro na EMERGÊNCIA: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def api_reset():
    stop_event.set()
    if not is_connected():
        return jsonify({"status": "erro", "message": "Sem conexão"}), 503
    try:
        for _ in range(2):
            write_register(20, 1)
            time.sleep(1)
            write_register(20, 0)
            time.sleep(1)
        logger.info("RESET executado")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Erro no RESET: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/posicionamento', methods=['POST'])
def api_posicionamento():

    if not is_connected():
        return jsonify({"status": "erro", "message": "Sem conexão"}), 503

    data = request.get_json(silent=True) or {}

    try:
        eixo = str(data.get('eixo', 'ambos')).lower()

        if eixo not in ('azi', 'tilt', 'ambos'):
            eixo = 'ambos'

        # =========================
        # AZIMUTE
        # =========================
        if eixo in ('azi', 'ambos') and data.get('posAzimute') is not None:

            pAzimute = float(data.get('posAzimute')) * 1000
            if pAzimute < 0:
                pAzimute = 360000 - abs(pAzimute)

            write_register(24, 2)
            time.sleep(0.02)
            write_register(28, 0)
            time.sleep(0.02)
            write_dword(70, int(pAzimute))
            write_register(50, int(APosAzi))
            write_register(52, int(MaxAccAzi))
            # write_register(72, int(VPosAzi))
            time.sleep(0.02)
            write_register(28, 4)

        # =========================
        # TILT
        # =========================
        if eixo in ('tilt', 'ambos') and data.get('posTilt') is not None:

            pTilt = float(data.get('posTilt')) * 1000

            if pTilt < 0:
                pTilt = 360000 - abs(pTilt)

            write_register(22, 2)
            time.sleep(0.02)
            write_register(26, 0)
            time.sleep(0.02)
            write_dword(60, int(pTilt))
            write_register(40, int(APosTilt))
            write_register(42, int(MaxAccTilt))
            # write_register(62, int(VPosTilt))
            time.sleep(0.02)
            write_register(26, 4)

        logger.info(f"Posicionamento ({eixo}) enviado com sucesso")

        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Erro no posicionamento: {e}")
        return jsonify({"erro": str(e)}), 500
    
@app.route('/api/hab_jog', methods=['POST'])
def api_hab_jog():

    if not is_connected():
        return jsonify({"status": "erro", "message": "Sem conexão"}), 503
    try:
        write_register(50, 10000)
        write_register(52, 10000)
        write_register(74, 10000)
        write_register(76, 10000)   
        write_register(56, 3000)

        write_register(40, 10000)
        write_register(42, 10000)
        write_register(64, 10000)
        write_register(66, 10000) 
        write_register(46, 3000)

        write_register(22, 0)
        write_register(24, 0)
        write_register(26, 0)
        write_register(28, 0)

        return jsonify({"status": "ok", "message": "Modo Jog habilitado"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/des_jog', methods=['POST'])
def api_des_jog():
    
    if not is_connected():
        return jsonify({"status": "erro", "message": "Sem conexão"}), 503
    try:
        write_register(22, 2)
        write_register(24, 2)
        write_register(26, 0)
        write_register(28, 0)
        return jsonify({"status": "ok", "message": "Modo Jog desabilitado"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/jog', methods=['POST'])
def api_jog():

    if not is_connected():
        return jsonify({"status": "erro", "message": "Sem conexão"}), 503

    data = request.get_json(silent=True) or {}

    try:
        eixo = data.get('eixo', 'ambos')  # 'azi', 'tilt', 'ambos'

        vel_azi_input = data.get('velAzimute')
        vel_tilt_input = data.get('velTilt')

        velAzimute = float(vel_azi_input) * 100.0 if vel_azi_input is not None else None
        velTilt    = float(vel_tilt_input) * 100.0 if vel_tilt_input is not None else None

        # ======================
        # HABILITAÇÃO GERAL
        # ======================

        write_register(40, 10000)
        write_register(42, 10000)
        write_register(50, 10000)
        write_register(52, 10000)
        write_register(22, 1)
        write_register(24, 1) 

        # ====================== TILT ======================
        if eixo in ('tilt', 'ambos') and velTilt is not None:

            if velTilt < 0:
                write_dword(46, int(abs(velTilt)))
                write_register(26, 2)
            elif velTilt > 0:
                write_dword(46, int(velTilt))
                write_register(26, 1)
            else:
                write_register(26, 0)

        # ====================== AZIMUTE ======================
        if eixo in ('azi', 'ambos') and velAzimute is not None:

            if velAzimute < 0:
                write_dword(56, int(abs(velAzimute)))
                write_register(28, 2)
            elif velAzimute > 0:
                write_dword(56, int(velAzimute))
                write_register(28, 1)
            else:
                write_register(28, 0)

        logger.info(
            f"JOG ({eixo}) → "
            f"Azi: {velAzimute/100 if velAzimute is not None else '---'} | "
            f"Tilt: {velTilt/100 if velTilt is not None else '---'}"
        )

        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Erro no jog: {e}")

@app.route('/api/jog_automatizada', methods=['POST'])
def api_jog_automatizada():

    if not is_connected():
        return jsonify({"status": "erro", "message": "Sem conexão"}), 503

    data = request.get_json()

    try:
        # =========================
        # RESET CONTROLES
        # =========================
        stop_event.clear()
        stop_azi.clear()
        stop_tilt.clear()

        eixo = data.get('eixo', 'ambos')

        inctime = float(data.get('inctime', 1))
        incveltilt = float(data.get('incveltilt', 0))
        incvelazi  = float(data.get('incvelazi', 0))
        velinitilt = float(data.get('velinitilt', 0))
        velendtilt = float(data.get('velendtilt', 0))
        veliniazi  = float(data.get('veliniazi', 0))
        velendazi  = float(data.get('velendazi', 0))

        # =========================
        # HELPERS
        # =========================
        def check_stop():
            if stop_event.is_set():
                raise InterruptedError()

        def safe_write(func, *args):
            check_stop()
            return func(*args)

        def normalize_inc(v0, v1, inc):
            if inc == 0:
                return 0
            return abs(inc) if v1 > v0 else -abs(inc)

        def calc_steps(v0, v1, inc):
            if inc == 0:
                return 0
            return int(abs((v1 - v0) / inc))

        # =========================
        # NORMALIZAÇÃO
        # =========================
        if eixo in ('tilt', 'ambos'):
            incveltilt = normalize_inc(velinitilt, velendtilt, incveltilt)

        if eixo in ('azi', 'ambos'):
            incvelazi = normalize_inc(veliniazi, velendazi, incvelazi)

        steps_tilt = calc_steps(velinitilt, velendtilt, incveltilt) if eixo in ('tilt', 'ambos') else 0
        steps_azi  = calc_steps(veliniazi, velendazi, incvelazi) if eixo in ('azi', 'ambos') else 0
        total_steps = max(steps_tilt, steps_azi)
        accveltilt = velinitilt
        accvelazi  = veliniazi


        # Config comum
        write_register(40, 10000)
        write_register(42, 10000)
        write_register(50, 10000)
        write_register(52, 10000)

        write_register(22, 1)
        write_register(24, 1)

        # =========================
        # ENVIO
        # =========================
        def send_velocity(v_tilt, v_azi):

            check_stop()

            # ===== TILT =====
            if eixo in ('tilt', 'ambos') and not stop_tilt.is_set():

                vTi = int(v_tilt * 100)
                vTi = max(min(vTi, 20000), -20000)

                if vTi < 0:
                    write_dword(46, abs(vTi))
                    write_register(26, 2)
                elif vTi > 0:
                    write_dword(46, vTi)
                    write_register(26, 1)
                else:
                    write_register(26, 0)

            # ===== AZI =====
            if eixo in ('azi', 'ambos') and not stop_azi.is_set():

                vAz = int(v_azi * 100)
                vAz = max(min(vAz, 50000), -50000)

                if vAz < 0:
                    write_dword(56, abs(vAz))
                    write_register(28, 2)
                elif vAz > 0:
                    write_dword(56, vAz)
                    write_register(28, 1)
                else:
                    write_register(28, 0)

        # =========================
        # PASSO 0
        # =========================
        send_velocity(accveltilt, accvelazi)

        logger.info(f"Passo 0/{total_steps} → Azi: {accvelazi:.1f} | Tilt: {accveltilt:.1f}")

        # =========================
        # LOOP
        # =========================
        for step in range(1, total_steps + 1):

            check_stop()

            # 🔴 INTERROMPE POR EIXO
            if eixo == 'azi' and stop_azi.is_set():
                logger.warning("Jog AZI interrompido")
                break

            if eixo == 'tilt' and stop_tilt.is_set():
                logger.warning("Jog TILT interrompido")
                break

            if eixo == 'ambos' and stop_azi.is_set() and stop_tilt.is_set():
                logger.warning("Jog AMBOS interrompido")
                break

            # ⏱️ WAIT INTERRUPTÍVEL
            elapsed = 0
            while elapsed < inctime:
                check_stop()
                time.sleep(0.1)
                elapsed += 0.1

            # ===== UPDATE =====
            if eixo in ('tilt', 'ambos') and step <= steps_tilt and not stop_tilt.is_set():
                accveltilt += incveltilt
                if (incveltilt > 0 and accveltilt > velendtilt) or \
                   (incveltilt < 0 and accveltilt < velendtilt):
                    accveltilt = velendtilt

            if eixo in ('azi', 'ambos') and step <= steps_azi and not stop_azi.is_set():
                accvelazi += incvelazi
                if (incvelazi > 0 and accvelazi > velendazi) or \
                   (incvelazi < 0 and accvelazi < velendazi):
                    accvelazi = velendazi

            send_velocity(accveltilt, accvelazi)

            logger.info(f"Passo {step}/{total_steps} → Azi: {accvelazi:.1f} | Tilt: {accveltilt:.1f}")

        logger.info("Jog automatizada finalizada")

        return jsonify({"status": "ok"})

    except InterruptedError:
        logger.warning("Jog automatizada interrompida com segurança")
        return jsonify({"status": "parado"})

    except Exception as e:
        logger.error(f"Erro na jog automatizada: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/executa_script', methods=['POST'])
def api_executa_script():
    global mark_counter, mark_total

    stop_event.clear()
    mark_counter = 0

    data = request.get_json(silent=True) or {}
    script_text = data.get('hiddentxt', '').strip()

    if not script_text:
        return jsonify({"status": "erro", "message": "Script vazio"})

    # =========================
    # 🔴 CALCULA TOTAL DE CICLOS (MARK)
    # =========================
    linhas = script_text.splitlines()
    mark_total = sum(1 for l in linhas if l.strip().upper().startswith("MARK"))

    logger.info(f"Total de ciclos (MARK): {mark_total}")

    # =========================
    # THREAD DE EXECUÇÃO
    # =========================
    threading.Thread(
        target=executa_script_worker,
        args=(script_text,),
        daemon=True,
        name="ScriptWorker"
    ).start()

    return jsonify({
        "status": "ok",
        "message": "Script iniciado",
        "total": mark_total
    })

@app.route('/api/le_tempo_script', methods=['POST'])
def api_le_tempo_script():

    data = request.get_json()
    script_text = data.get('hiddentxt', '').strip()

    if not script_text:
        return jsonify({"tempoLido": 0})

    linhas = script_text.splitlines()

    tempo_total = 0.0

    tempo_mov_azi = 0.0
    tempo_mov_tilt = 0.0

    pos_azi = 0.0
    pos_tilt = 0.0

    # =========================
    # PARÂMETROS (MESMOS DO SIMULADOR)
    # =========================
    ACC = 100.0          # °/s²
    CRUISE = 30.0        # °/s

    # =========================
    # MENOR CAMINHO ANGULAR
    # =========================
    def delta_angular(a, b):
        return (a - b + 180) % 360 - 180

    # =========================
    # TEMPO COM ACELERAÇÃO (TRAPEZOIDAL)
    # =========================
    def tempo_mov(delta):

        d = abs(delta)

        if d < 1e-6:
            return 0.0

        # tempo para atingir velocidade de cruzeiro
        t_acc = CRUISE / ACC
        d_acc = 0.5 * ACC * t_acc**2

        # perfil triangular (não atinge cruzeiro)
        if d < 2 * d_acc:
            return 2 * (d / ACC) ** 0.5

        # perfil trapezoidal
        d_cruise = d - 2 * d_acc
        t_cruise = d_cruise / CRUISE

        return 2 * t_acc + t_cruise

    # =========================
    # LOOP
    # =========================
    for linha in linhas:

        linha = linha.strip()

        if not linha or linha.startswith('#'):
            continue

        partes = linha.split()
        cmd = partes[0].upper()

        if cmd == 'AZPOS' and len(partes) > 1:
            nova = float(partes[1])
            delta = delta_angular(nova, pos_azi)
            tempo_mov_azi = tempo_mov(delta)
            pos_azi = (pos_azi + delta) % 360
            continue

        if cmd == 'TLPOS' and len(partes) > 1:
            nova = float(partes[1])
            delta = delta_angular(nova, pos_tilt)
            tempo_mov_tilt = tempo_mov(delta)
            pos_tilt = (pos_tilt + delta) % 360
            continue

        if cmd == 'WAIT' and len(partes) > 1:

            wait_time = float(partes[1])

            # 🔴 REGRA CORRETA: WAIT domina
            tempo_total += max(
                tempo_mov_azi,
                tempo_mov_tilt,
                wait_time
            )

            tempo_mov_azi = 0.0
            tempo_mov_tilt = 0.0

            continue

        # (opcional) ignorar MARK ou outros comandos
        if cmd == 'MARK':
            continue

    # =========================
    # ÚLTIMO MOVIMENTO
    # =========================
    tempo_total += max(tempo_mov_azi, tempo_mov_tilt)

    return jsonify({
        "tempoLido": tempo_total / 60.0
    })

@app.route('/api/mark_status', methods=['GET'])
def api_mark_status():
    return jsonify({
        "count": mark_counter,
        "total": mark_total
    })

@app.route('/api/salvar_local', methods=['POST'])
def salvar_local():
    data = request.get_json()
    conteudo = data.get('conteudo', '')

    caminho = salvar_script_local(conteudo)

    return jsonify({"caminho": caminho})

@app.route('/api/config', methods=['GET'])
def api_get_config():

    try:
        logger.info("🔥 /api/config GET CHAMADO")

        # ==============================
        # SEM CONEXÃO → usa JSON direto
        # ==============================
        if not is_connected():
            logger.warning("Sem conexão Modbus - usando config local")

            config = load_config()

            return jsonify({
                "status": "warning",
                "message": "Sem conexão com a mesa. Usando valores locais.",
                "conectado": False,
                **config
            }), 200

        # ==============================
        # COM CONEXÃO → lê da mesa
        # ==============================
        data = {
            "velPosAzimute": read_param("velPosAzimute"),
            "accPosAzimute": read_param("accPosAzimute"),
            "maxVelAzimute": read_param("maxVelAzimute"),
            "maxAccAzimute": read_param("maxAccAzimute"),

            "velPosTilt": read_param("velPosTilt"),
            "accPosTilt": read_param("accPosTilt"),
            "maxVelTilt": read_param("maxVelTilt"),
            "maxAccTilt": read_param("maxAccTilt"),
        }

        # ==============================
        # COMPLEMENTA COM CONFIG LOCAL
        # (somente dados do simulador)
        # ==============================
        config_local = load_config()

        for key in [
            "posIniAzimute",
            "posIniTilt",
            "velIniAzimute",
            "velIniTilt",
            "K",
            "DT"
        ]:
            data[key] = config_local.get(key)

        logger.info("✅ Configuração unificada carregada (mesa + JSON)")

        return jsonify({
            "status": "ok",
            "conectado": True,
            **data
        })

    except Exception as e:
        logger.error(f"Erro em /api/config: {e}")

        # ==============================
        # FALLBACK → JSON
        # ==============================
        config = load_config()

        return jsonify({
            "status": "partial",
            "message": "Erro ao ler da mesa. Usando fallback.",
            "conectado": False,
            **config
        }), 200

@app.route('/api/config', methods=['POST'])
def api_set_config():
    global VPosAzi, APosAzi, MaxVelAzi, MaxAccAzi
    global VPosTilt, APosTilt, MaxVelTilt, MaxAccTilt

    try:
        data = request.get_json()

        VPosAzi = float(data.get('velPosAzimute', VPosAzi))
        APosAzi = float(data.get('accPosAzimute', APosAzi))
        MaxVelAzi = float(data.get('maxVelAzimute', MaxVelAzi))
        MaxAccAzi = float(data.get('maxAccAzimute', MaxAccAzi))

        VPosTilt = float(data.get('velPosTilt', VPosTilt))
        APosTilt = float(data.get('accPosTilt', APosTilt))
        MaxVelTilt = float(data.get('maxVelTilt', MaxVelTilt))
        MaxAccTilt = float(data.get('maxAccTilt', MaxAccTilt))

        save_config()

        logger.info(f"Configurações atualizadas localmente → Azi V={VPosAzi:.1f} | Tilt V={VPosTilt:.1f}")

        if not is_connected():
            return jsonify({
                "status": "warning",
                "message": "Salvo localmente. Mesa desconectada.",
                "conectado": False
            }), 200

        # ====================== ENVIO PARA A MESA (igual ao C original Infax) ======================
        try:
            # Azimute
            write_register(72, int(VPosAzi * 100))
            write_register(74, int(APosAzi * 100))
            write_register(50, int(APosAzi * 100))
            write_register(52, int(APosAzi * 100))
            write_register(90, int(MaxVelAzi * 100))
            write_register(92, int(MaxAccAzi * 100))

            # Tilt
            write_register(62, int(VPosTilt * 100))
            write_register(64, int(APosTilt * 100))
            write_register(40, int(APosTilt * 100))
            write_register(42, int(APosTilt * 100))
            write_register(80, int(MaxVelTilt * 100))
            write_register(82, int(MaxAccTilt * 100))

            # Comando extra não mapeado
            write_register(20, 2)
            time.sleep(1)
            write_register(20, 0)

            logger.info("✅ Configurações enviadas para a mesa com sucesso")
            return jsonify({
                "status": "ok",
                "message": "Configurações salvas e aplicadas na mesa",
                "conectado": True
            })

        except Exception as e:
            logger.error(f"Erro ao escrever na mesa: {e}")
            return jsonify({
                "status": "partial",
                "message": "Salvo localmente, mas falha ao enviar para a mesa",
                "conectado": True
            }), 200

    except Exception as e:
        logger.error(f"Erro ao processar setConfig: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/raw', methods=['POST'])
def api_raw():

    if not is_connected():
        return jsonify({"status": "warning", "message": "Sem conexão"}), 200

    try:
        data = request.get_json()
        cmd = data.get("command", "").strip()

        if not cmd:
            return jsonify({"status": "error", "message": "Comando vazio"}), 400

        parts = cmd.split()
        op = parts[0].upper()

        # ==========================================================
        # READ (endereço direto)
        # ==========================================================
        if op == "READ" and len(parts) == 2:
            addr = int(parts[1])

            hr = read_hr(addr)
            ir = read_ir(addr)

            return jsonify({
                "status": "ok",
                "message": f"HR[{addr}]={hr} | IR[{addr}]={ir}"
            })

        # ==========================================================
        # WRITE (endereço direto)
        # ==========================================================
        elif op == "WRITE" and len(parts) == 3:
            addr = int(parts[1])
            value = int(parts[2])

            # proteção básica
            if addr < 0 or addr > 200:
                return jsonify({"status": "error", "message": "Endereço fora da faixa"}), 400

            write_hr(addr, value)

            return jsonify({
                "status": "ok",
                "message": f"HR[{addr}] ← {value}"
            })

        # ==========================================================
        # READ Mnemônico
        # ==========================================================
        elif op == "R" and len(parts) == 2:
            name = resolve_name(parts[1])

            if not name:
                return jsonify({"status": "error", "message": "Parâmetro inválido"}), 400

            reg = REG_MAP[name]

            hr = read_hr(reg["addr"])
            ir = read_ir(reg["addr"])

            scaled = (hr if reg["type"] == "HR" else ir) / reg["scale"]

            return jsonify({
                "status": "ok",
                "message": f"{reg['alias']} → {scaled:.2f} (HR={hr} | IR={ir})"
            })

        # ==========================================================
        # WRITE Mnemônico
        # ==========================================================
        elif op == "W" and len(parts) == 3:
            name = resolve_name(parts[1])

            if not name:
                return jsonify({"status": "error", "message": "Parâmetro inválido"}), 400

            value = float(parts[2])
            reg = REG_MAP[name]

            if reg["type"] != "HR":
                return jsonify({"status": "error", "message": "Parâmetro não gravável"}), 400

            raw = int(value * reg["scale"])
            write_hr(reg["addr"], raw)

            return jsonify({
                "status": "ok",
                "message": f"{reg['alias']} ← {value} (raw={raw})"
            })

        # ==========================================================
        else:
            return jsonify({
                "status": "error",
                "message": "Use: READ addr | WRITE addr val | R nome | W nome val"
            }), 400

    except Exception as e:
        logger.error(f"RAW erro: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/dadosMesa.txt')
def dados_mesa():
    response = make_response(send_file('dadosMesa.txt'))
    response.headers['Cache-Control'] = 'no-store'
    return response

# ====================== INTERFACE HTML em /templates/index.html ======================
@app.route("/")
def index():
    return render_template(
        "index.html",
        modbus_ip=SERVER,
        modbus_port=MODBUS_PORT
    )

# ====================== MAIN ======================
if __name__ == '__main__':
    logger.info("=== Mesa Inercial 2 Eixos - Versão Industrial Hardened (COMPLETA) ===")
    logger.info(f"Web → http://0.0.0.0:{WEB_PORT}")
    logger.info(f"Log → {LOG_FILE}")


    # Inicia a thread de reconexão
    reconnect_thread = threading.Thread(target=try_reconnect, daemon=True, name="Reconnect")
    reconnect_thread.start()

    time.sleep(2.0)

    if is_connected():
        config = load_config()
        apply_config(config)
    else:
        logger.info("Mesa não conectada no startup. Usando valores do arquivo JSON.")

    signal.signal(signal.SIGINT, shutdown_gracefully)
    signal.signal(signal.SIGTERM, shutdown_gracefully)

    # ==========  SILENCIAR FLASK  =============
    # Muito verboso mesmo com debug desativado
    logging.getLogger('werkzeug').disabled = True          # Remove os logs de acesso (GET/POST)
    app.logger.disabled = True                             # Remove logs internos do Flask

    # Finalmente inicia o servidor
    app.run(
        host='0.0.0.0', 
        port=WEB_PORT, 
        debug=False, 
        threaded=True, 
        use_reloader=False
    )
