'''
# BACKUP DA VERSÃO ANTERIOR #

from pymodbus.client import ModbusTcpClient
import time
import json


SERVER_PROD = "192.168.1.1"
MODBUS_PORT_PROD = 502

SERVER_TEST = "127.0.0.1"
MODBUS_PORT_TEST = 5020

CONFIG_FILE = "mesa_config.json"


class RotTableWrapper:
    """
    RotTableWrapper
    ===============

    Interface de alto nível para controle de mesa inercial (YAW / ROLL)
    via Modbus TCP.

    --------------------------------------------------------------------
    LIMITES FÍSICOS
    --------------------------------------------------------------------
    YAW  : 500 °/s
    ROLL : 200 °/s
    ACC  : 100 °/s²

    --------------------------------------------------------------------
    ESCALAS DO CONTROLADOR
    --------------------------------------------------------------------
    Velocidade → valor * 100
    Posição    → valor * 1000

    ====================================================================
    COMMAND FLOW (ESPECIFICAÇÃO COMPLETA)
    ====================================================================

    Command Flow Summary
    --------------------

    MOVE:
        prepare → mode → position → delay → trigger

    JOG:
        prepare → velocity → direction

    READ:
        read → convert → return

    STOP:
        direction = 0
    
    --------------------------------------------------------------------
    1. PREPARAÇÃO (BASE PARA MOVE E JOG)
    --------------------------------------------------------------------
    prepare_yaw_motion() / prepare_roll_motion()

        write(addr_acc, acceleration_reg_value)
        write(addr_maxacc, max_acceleration_reg_value)

        write(22, 1)                # enable roll
        delay(0.1)                 ⚠️ CRÍTICO

        write(24, 1)                # enable yaw
        delay(0.1)                 ⚠️ CRÍTICO

    prepare_all_motion()
        → chama prepare_yaw_motion()
        → chama prepare_roll_motion()

    --------------------------------------------------------------------
    2. MOVE (POSICIONAMENTO ABSOLUTO)
    --------------------------------------------------------------------

    ▶ move_yaw(angle)

        prepare_yaw_motion()

        write(24, 2)                # position mode yaw
        write(28, 0)                # stop

        write_dword(70, position)

        delay(0.02)

        write(28, 4)                # trigger

    ------------------------------------------------------------

    ▶ move_roll(angle)

        prepare_roll_motion()

        write(22, 2)                # position mode roll
        write(26, 0)                # stop

        write_dword(60, position)

        delay(0.02)

        write(26, 4)                # trigger

    ------------------------------------------------------------

    ▶ move_all(angle)

        prepare_all_motion()

        write(24, 2)
        write(22, 2)

        write(28, 0)
        write(26, 0)

        write_dword(70, position yaw)
        write_dword(60, position roll)

        delay(0.02)

        write(28, 4)        # trigger yaw
        write(26, 4)        # trigger roll

    --------------------------------------------------------------------
    3. JOG (VELOCIDADE CONTÍNUA)
    --------------------------------------------------------------------

    ▶ jog_yaw(vel)

        prepare_yaw_motion()

        write_dword(56, |vel|)

        if vel > 0 → write(28, 1)   # trigger positivo
        if vel < 0 → write(28, 2)   # trigger negativo
        if vel == 0 → write(28, 0)  #trigger stop

    ------------------------------------------------------------

    ▶ jog_roll(vel)

        prepare_roll_motion()

        write_dword(46, |vel|)

        if vel > 0 → write(26, 1)   # trigger positivo
        if vel < 0 → write(26, 2)   # trigger negativo
        if vel == 0 → write(26, 0)  # trigger stop

    ------------------------------------------------------------

    ▶ jog_all(vel)

        prepare_all_motion()

        write_dword(56, |vel|)
        write_dword(46, |vel|)

        direção yaw (trigger):
            vel > 0 → write(28, 1)
            vel < 0 → write(28, 2)
            vel == 0 → write(28, 0)

        direção roll (trigger):
            vel > 0 → write(26, 1)  # trigger positivo
            vel < 0 → write(26, 2)  # trigger negativo
            vel == 0 → write(26, 0) # trigger stop

    --------------------------------------------------------------------
    4. STOP
    --------------------------------------------------------------------

    ▶ stop_yaw()
        write(28, 0) # trigger stop

    ▶ stop_roll()
        write(26, 0) # trigger stop

    ▶ stop_all()
        write(28, 0) # trigger stop yaw
        write(26, 0) # trigger stop roll

    --------------------------------------------------------------------
    5. LEITURA (FEEDBACK) - MODBUS - (16 bit protocol)
    --------------------------------------------------------------------

    ▶ get_yaw()

        read_input(0, 2)
        value = (MSB << 16) | LSB
        return value / 1_000_000

    ------------------------------------------------------------

    ▶ get_roll()

        read_input(4, 2)
        value = (MSB << 16) | LSB
        return value / 1_000_000

    ------------------------------------------------------------

    ▶ get_all_axes()

        yaw  = get_yaw()
        roll = get_roll()

        return (yaw, roll)

    --------------------------------------------------------------------
    6. EMERGENCY
    --------------------------------------------------------------------

    ▶ emergency_stop()

        write(20, 4)
        delay(0.2)
        write(20, 0)

    ------------------------------------------------------------

    ▶ reset_emergency()

        write(20, 1)
        delay(0.2)
        write(20, 0)

    ====================================================================
    OBSERVAÇÕES IMPORTANTES
    ====================================================================

    - Cada comando é executado como sequência discreta
    - Delays de 0.1 s são obrigatórios na preparação
    - Delay de 0.02 s é necessário antes do trigger de posição
    - STOP atua apenas zerando o comando de direção
    - Métodos *_all executam comandos para ambos eixos
    - Conversões:
        posição → / 1_000_000           # mesa para o PC
        velocidade → * 100 (entrada)    # PC para a mesa

    ====================================================================
    ARQUITETURA (CAMADAS)
    ====================================================================

    NÍVEL 1 (CORE)
        write / write_dword / read_input

    NÍVEL 2 (PRIMITIVOS)
        set_* / normalize / clip

    NÍVEL 3 (SEQUÊNCIA)
        prepare_* / move_* / jog_* / stop_* / get_*

    """

    def __init__(self, host=SERVER_PROD, port=MODBUS_PORT_PROD):
        """
        Inicializa cliente Modbus.

        Parameters
        ----------
        host : str
            Endereço IP do controlador.
        port : int
            Porta Modbus TCP.
        """
        self.client = ModbusTcpClient(host=host, port=port)

        """ Configurações iniciais (valores padrão) - podem ser alterados antes de aplicar com set_config()
            depois de usar os métodos individuais para alterar os valores, ou diretamente editando os atributos públicos, é necessário chamar set_config() para aplicar as mudanças e salvar a configuração atualizada no arquivo JSON.
        """

        # Fator de escala para conversão de unidades 
        # (ajustado para refletir a escala real usada nos registradores)
        self.FACTOR = 100

        # Configuração Padrão da Mesa Inercial
        self.yaw_acceleration_value = int(100.0) # °/s²
        self.roll_acceleration_value = int(100.0) # °/s²
        self.yaw_max_acceleration_value = int(100.0) # °/s²
        self.roll_max_acceleration_value = int(100.0) # °/s²
        self.yaw_move_velocity_value = int(30.0) # °/s
        self.roll_move_velocity_value = int(30.0) # °/s
        self.yaw_move_max_velocity_value = int(500.0) # °/s
        self.roll_move_max_velocity_value = int(200.0) # °/s

        print(f"Dejesa salvar a configuração padrão da mesa no arquivo mesa_config.? (s/N)")
        choice = input().strip().lower()
        if choice == '':
            choice = 'n'
        if choice == "s":
            self.save_configToFile()
        
        print(f"CONFIGURAÇÃO ATUAL DA MESA INERCIAL\nYAW_ACC={self.yaw_acceleration_value:.2f} °/s²\nROLL_ACC={self.roll_acceleration_value:.2f} °/s²\nYAW_MAX_ACC={self.yaw_max_acceleration_value:.2f} °/s²\nROLL_MAX_ACC={self.roll_max_acceleration_value:.2f} °/s²\nYAW_MOVE_VEL={self.yaw_move_velocity_value:.2f} °/s\nROLL_MOVE_VEL={self.roll_move_velocity_value:.2f} °/s\nYAW_MAX_VEL={self.yaw_move_max_velocity_value:.2f} °/s\nROLL_MAX_VEL={self.roll_move_max_velocity_value:.2f} °/s  ")
        print(f"Deseja enviar a configuração atual para a mesa? (s/N)")
        choice = input().strip().lower()
        if choice == '':
            choice = 'n'
        if choice == "s":
            self.apply_configToTable()

    # =====================================================
    # CONNECTION
    # =====================================================

    def connect(self):
        """
        Abre conexão Modbus.

        Parameters
        ----------
        None

        Returns
        -------
        bool
        """
        return self.client.connect()

    def close(self):
        """
        Fecha conexão Modbus.

        Parameters
        ----------
        None
        """
        self.client.close()

    def _ensure(self):
        """
        Garante conexão ativa.

        Parameters
        ----------
        None
        """
        if not self.client.connected:
            self.client.connect()

    # =====================================================
    # CORE MODBUS
    # =====================================================

    def write(self, addr, value):
        """
        Escreve registrador 16 bits.

        Parameters
        ----------
        addr : int
            Endereço do registrador.
        value : int
            Valor a ser escrito.
        """
        self._ensure()
        return self.client.write_register(address=addr, value=int(value))

    def write_dword(self, addr, value):
        """
        Escreve valor 32 bits.

        Parameters
        ----------
        addr : int
            Endereço base (LSB).
        value : int
            Valor 32 bits.
        """
        value = int(value)
        low = value & 0xFFFF
        high = (value >> 16) & 0xFFFF

        self.write(addr, low)
        self.write(addr + 1, high)

    def read_input(self, addr, count=2):
        """
        Lê registradores de entrada.

        Parameters
        ----------
        addr : int
            Endereço inicial.
        count : int
            Quantidade de registradores.
        """
        self._ensure()
        return self.client.read_input_registers(address=addr, count=count)

    def read_dword(self, addr):
        """
        Lê valor 32 bits.

        Parameters
        ----------
        addr : int
            Endereço base.
        """
        r = self.read_input(addr, 2)
        if r.isError():
            return None
        return (r.registers[1] << 16) | r.registers[0]

    # =====================================================
    # UTILS
    # =====================================================

    def to_int32(self, raw):
        """
        Converte valor 32 bits para inteiro com sinal.
        Parameters
        ----------
        raw : int
            Valor 32 bits.

        Returns
        -------
        int : Valor com sinal.
        """
        if raw & 0x80000000:
            return raw - 0x100000000
        return raw

    def set_config(self):
        """
        Aplica configurações de movimentos da mesa.
        Obs.: Sem estes comandos: os registradores
              são alterados, mas a configuração não é aplicada:
            self.write(20, 2)
            time.sleep(1)
            self.write(20, 0)
        
        Parameters
        ----------
        None
        """

        print("Se nada foi alterado, valores padrão serão aplicados.")
        print(f"Valores atuais\nYAW_ACC={self.yaw_acceleration_value:.2f} °/s²\nROLL_ACC={self.roll_acceleration_value:.2f} °/s²\nYAW_MAX_ACC={self.yaw_max_acceleration_value:.2f} °/s²\nROLL_MAX_ACC={self.roll_max_acceleration_value:.2f} °/s²\nYAW_MOVE_VEL={self.yaw_move_velocity_value:.2f} °/s\nROLL_MOVE_VEL={self.roll_move_velocity_value:.2f} °/s\nYAW_MAX_VEL={self.yaw_move_max_velocity_value:.2f} °/s\nROLL_MAX_VEL={self.roll_move_max_velocity_value:.2f} °/s  ")
        print("Tem certeza que deseja aplicar estas configurações? (s/N)")
        response = input().strip().lower()
        if response == '':
            response = 'n'
        if response != 's':
            print("Configurações não aplicadas.")
            return

        self.set_yaw_acceleration(self.yaw_acceleration_value)
        self.set_roll_acceleration(self.roll_acceleration_value)
        self.set_yaw_max_acceleration(self.yaw_max_acceleration_value)
        self.set_roll_max_acceleration(self.roll_max_acceleration_value)
        self.set_yaw_move_max_velocity(self.yaw_move_max_velocity_value)
        self.set_roll_move_max_velocity(self.roll_move_max_velocity_value)
        self.set_yaw_move_velocity(self.yaw_move_velocity_value)
        self.set_roll_move_velocity(self.roll_move_velocity_value)

        self.save_configToFile()

    def apply_configToTable(self):
        """Aplica configurações de movimento da mesa.
        Obs.: Sem estes comandos: os registradores  são alterados, mas a configuração não é aplicada:
            self.write(20, 2)
            time.sleep(1)
            self.write(20, 0)
        Parameters
        ----------  
        None
        """

        # YAW 
        self.write(50, self.yaw_acceleration_value * self.FACTOR)
        self.write(52, self.yaw_max_acceleration_value * self.FACTOR)
        self.write(72, self.yaw_move_velocity_value * self.FACTOR)
        self.write(74, self.yaw_acceleration_value * self.FACTOR)
        self.write(76, self.yaw_max_acceleration_value * self.FACTOR)
        self.write(90, self.yaw_move_max_velocity_value * self.FACTOR)
        self.write(92, self.yaw_max_acceleration_value * self.FACTOR)

        # ROLL
        self.write(40, self.roll_acceleration_value * self.FACTOR)
        self.write(42, self.roll_max_acceleration_value * self.FACTOR)
        self.write(62, self.roll_move_velocity_value * self.FACTOR)
        self.write(64, self.roll_acceleration_value * self.FACTOR)
        self.write(66, self.roll_max_acceleration_value * self.FACTOR)
        self.write(80, self.roll_move_max_velocity_value * self.FACTOR)
        self.write(82, self.roll_max_acceleration_value * self.FACTOR)

        # Comando de aplicação - específico da programção PLC (sem acesso) do controlador
        self.write(20, 2)
        time.sleep(1)
        self.write(20, 0)

    def save_configToFile(self, CONFIG_FILE=CONFIG_FILE):
        data = {
            # ==============================
            # POSICIONAMENTO (PADRÃO UNIFICADO)
            # ==============================
            "velPosAzimute": float(self.yaw_move_velocity_value),
            "accPosAzimute": float(self.yaw_acceleration_value),
            "maxVelAzimute": float(self.yaw_move_max_velocity_value),
            "maxAccAzimute": float(self.yaw_max_acceleration_value),

            "velPosTilt": float(self.roll_move_velocity_value),
            "accPosTilt": float(self.roll_acceleration_value),
            "maxVelTilt": float(self.roll_move_max_velocity_value),
            "maxAccTilt": float(self.roll_max_acceleration_value),

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

        except Exception as e:
            print(f"Falha ao salvar config: {e}")

    def normalize(self, deg):
        """
        Normaliza ângulo. Evita valores negativos, convertendo para faixa [0, 360°].

        Parameters
        ----------
        deg : float
            Ângulo em graus.
        """
        v = int(deg * 1000)
        return 360000 - abs(v) if v < 0 else v

    def clip_vel_yaw(self, vel):
        """
        Limita velocidade YAW. Max = 200.0 °/s

        Parameters
        ----------
        vel : float
        """
        return max(-self.yaw_move_max_velocity_value, min(self.yaw_move_max_velocity_value, vel))

    def clip_vel_roll(self, vel):
        """
        Limita velocidade ROLL. Max = 200.0 °/s

        Parameters
        ----------
        vel : float
        """
        return max(-self.roll_move_max_velocity_value, min(self.roll_move_max_velocity_value, vel))

    def clip_acc_yaw(self, acc):
        """
        Limita aceleração YAW. Max = 100.0 °/s²

        Parameters
        ----------
        acc : float
        """
        return max(-self.yaw_max_acceleration_value, min(self.yaw_max_acceleration_value, acc))

    def clip_acc_roll(self, acc):
        """
        Limita aceleração ROLL. Max = 100.0 °/s²

        Parameters
        ----------
        acc : float
        """
        return max(-self.roll_max_acceleration_value, min(self.roll_max_acceleration_value, acc))

    # =================================================================================
    # INICIALIZAÇÃO DAS VARIÁVEIS DE CONFIGURAÇÃO DE MOVIMENTO. PARA APLICAR OS VALORES
    # DEFINIDOS, É NECESSÁRIO CHAMAR set_config() APÓS USAR ESTES MÉTODOS OU EDITAR OS 
    # ATRIBUTOS PÚBLICOS DIRETAMENTE E CHAMAR set_config() PARA APLICAR AS MUDANÇAS.
    # VALORES PADRÃO SÃO DEFINIDOS NO CONSTRUTOR, E PODEM SER SALVOS NO ARQUIVO JSON 
    # NA INICIALIZAÇÃO.
    # =================================================================================

    def set_yaw_move_velocity(self, vel):
        """
        Define a variável velocidade de movimento YAW (usada no modo Posicionamento Absoluto).

        Parameters
        ----------
        vel : float
        addr_vel : int
        """
        v = int(self.clip_vel_yaw(vel))
        self.yaw_move_velocity_value = v
       
    def set_roll_move_velocity(self, vel):
        """
        Define a variável velocidade de movimento ROLL (usada no modo Posicionamento Absoluto).

        Parameters
        ----------
        vel : float
        addr_vel : int
        """
        v = int(self.clip_vel_roll(vel))
        self.roll_move_velocity_value = v
    
    def set_yaw_move_max_velocity(self, vel):
        """
        Define variável velocidade máxima de movimento YAW (usada no modo Posicionamento Absoluto).

        Parameters
        ----------
        vel : float
        addr_max_vel : int
        """
        v = int(self.clip_vel_yaw(vel))
        self.yaw_move_max_velocity_value = v
    
    def set_roll_move_max_velocity(self, vel):
        """
        Define a variável velocidade máxima de movimento ROLL (usada no modo Posicionamento Absoluto).

        Parameters
        ----------
        vel : float
        addr_max_vel : int
        """
        v = int(self.clip_vel_roll(vel))
        self.roll_move_max_velocity_value = v

    def set_yaw_acceleration(self, acc):
        """
        Define a variável aceleração YAW.

        Parameters
        ----------
        acc : float
        addr_acc : int
        """
        a = int(self.clip_acc_yaw(acc))
        self.yaw_acceleration_value = a
        
    def set_roll_acceleration(self, acc):
        """
        Define a variável aceleração ROLL.

        Parameters
        ----------
        acc : float
        addr_acc : int
        """
        a = int(self.clip_acc_roll(acc))  
        self.roll_acceleration_value = a
    
    def set_yaw_max_acceleration(self, acc):
        """
        Define a variável aceleração máxima YAW.

        Parameters
        ----------
        acc : float
        addr_max_acc : int
        """
        a = int(self.clip_acc_yaw(acc))
        self.yaw_max_acceleration_value = a
       
    def set_roll_max_acceleration(self, acc):
        """
        Define a variável aceleração máxima ROLL.

        Parameters
        ----------
        acc : float
        addr_max_acc : int
        """
        a = int(self.clip_acc_roll(acc))
        self.roll_max_acceleration_value = a

    def set_yaw_velocity(self, vel):
        """
        Define a variável velocidade YAW.

        Parameters
        ----------
        vel : float
        addr_vel : int

        Returns 
        -------
        int : Velocidade aplicada (após clipping e escala)
        """
        v = int(self.clip_vel_yaw(vel))
        self.yaw_move_velocity_value = v

    def set_roll_velocity(self, vel):
        """
        Define a variável velocidade ROLL.

        Parameters
        ----------
        vel : float
        addr_vel : int

        Returns
        -------
        int : Velocidade aplicada (após clipping e escala)

        """
        v = int(self.clip_vel_roll(vel))
        self.roll_move_velocity_value = v

    # =====================================================
    # PREPARAÇÃO
    # =====================================================

    def prepare_yaw_motion(self,
                           addr_acc=40,
                           addr_max_acc=42,
                           addr_enable_roll=22,
                           addr_enable_yaw=24):
        """
        Prepara YAW.

        Parameters
        ----------
        addr_acc : int
        addr_maxacc : int  : Max Acceleration (opcional, pode ser o mesmo de addr_acc)
        addr_enable_roll : int : Acceleration enable ROLL (deve ser 1 para permitir movimento)
        addr_enable_yaw : int : Acceleration enable YAW (deve ser 1 para permitir movimento)
        """
        self.write(addr_acc, self.yaw_acceleration_value)
        self.write(addr_max_acc, self.yaw_max_acceleration_value)
        self.write(addr_enable_roll, 1)
        time.sleep(0.1) # This delay may not be removed or decreased
        self.write(addr_enable_yaw, 1)
        time.sleep(0.1) # This delay may not be removed or decreased

    def prepare_roll_motion(self,
                            addr_acc=50,
                            addr_max_acc=52,
                            addr_enable_roll=22,
                            addr_enable_yaw=24):
        """
        Prepara ROLL.

        Parameters
        ----------
        addr_acc : int
        addr_maxacc : int  : Max Acceleration (opcional, pode ser o mesmo de addr_acc)
        addr_enable_roll : int : Acceleration enable ROLL (deve ser 1 para permitir movimento)
        addr_enable_yaw : int : Acceleration enable YAW (deve ser 1 para permitir movimento)
        """
        self.write(addr_acc, self.roll_acceleration_value)
        self.write(addr_max_acc, self.roll_max_acceleration_value)
        self.write(addr_enable_roll, 1)
        time.sleep(0.1) # This delay may not be removed or decreased
        self.write(addr_enable_yaw, 1)
        time.sleep(0.1) # This delay may not be removed or decreased

    def prepare_all_motion(self):
        """
        Prepara ambos os eixos.

        Parameters
        ----------
        None
        """
        self.prepare_yaw_motion()
        self.prepare_roll_motion()

    # =====================================================
    # MÉTODOS SIMPLES
    # =====================================================

    def set_yaw_direction(self, direction, addr_cmd=28):
        """
        Define direção YAW.

        Parameters
        ----------
        direction : int : 0 = stop, 1 = positivo, 2 = negativo, 4 = modo posição
        addr_cmd : int
        """
        self.write(addr_cmd, direction) # trigger

    def set_roll_direction(self, direction, addr_cmd=26):
        """
        Define direção ROLL.

        Parameters
        ----------
        direction : int : 0 = stop, 1 = positivo, 2 = negativo, 4 = modo posição
        addr_cmd : int
        """
        self.write(addr_cmd, direction) # trigger

    def set_yaw_position(self, angle, addr_pos=70):
        """
        Define a variável posição YAW.

        Parameters
        ----------
        angle : float
        addr_pos : int
        """
        self.write_dword(addr_pos, self.normalize(angle))

    def set_roll_position(self, angle, addr_pos=60):
        """
        Define a variável posição ROLL.

        Parameters
        ----------
        angle : float
        addr_pos : int
        """
        self.write_dword(addr_pos, self.normalize(angle))

    def set_position_mode_yaw(self, addr_enable=24):
        """
        Modo posição YAW.

        Parameters
        ----------
        addr_enable : int : Registrador de habilitação do modo posição (deve ser 0 para desabilitar, 1 para permitir movimento,  2 para resetar)
        """
        self.write(addr_enable, 2)

    def set_position_mode_roll(self, addr_enable=22):
        """
        Modo posição ROLL.

        Parameters
        ----------
        addr_enable : int : Registrador de habilitação do modo posição (deve ser 0 para desabilitar, 1 para permitir movimento,  2 para resetar)
        """
        self.write(addr_enable, 2)

    # =====================================================
    # JOG - VELOCIDADE CONTÍNUA
    # =====================================================

    def jog_yaw(self, vel):
        """
        Movimento contínuo YAW.

        Parameters
        ----------
        vel : float
        """
        self.prepare_yaw_motion()
        v = self.set_yaw_velocity(vel)

        if v > 0:
            self.set_yaw_direction(1) # trigger modo jog sentido positivo
        elif v < 0:
            self.set_yaw_direction(2) # trigger modo jog sentido negativo
        else:
            self.set_yaw_direction(0) # trigger stop

    def jog_roll(self, vel):
        """
        Movimento contínuo ROLL.

        Parameters
        ----------
        vel : float
        """
        self.prepare_roll_motion()
        v = self.set_roll_velocity(vel)

        if v > 0:
            self.set_roll_direction(1) # trigger modo jog sentido positivo
        elif v < 0:
            self.set_roll_direction(2) # trigger modo jog sentido negativo
        else:
            self.set_roll_direction(0) # trigger modo jog stop

    def jog_all(self, vel):
        """
        Movimento simultâneo.

        Parameters
        ----------
        vel : float
        """
        self.prepare_all_motion()

        v_yaw = self.set_yaw_velocity(vel)
        v_roll = self.set_roll_velocity(vel)

        self.set_yaw_direction(1 if v_yaw > 0 else 2 if v_yaw < 0 else 0)
        self.set_roll_direction(1 if v_roll > 0 else 2 if v_roll < 0 else 0)

    # =====================================================
    # MOVE - POSICIONAMENTO ABSOLUTO
    # =====================================================

    def move_yaw(self, angle):
        """
        Move YAW.

        Parameters
        ----------
        angle : float
        """
        self.prepare_yaw_motion()

        self.set_position_mode_yaw()
        self.set_yaw_direction(0)
        self.set_yaw_position(angle)

        time.sleep(0.02)
        self.set_yaw_direction(4) # trigger modo posição

    def move_roll(self, angle):
        """
        Move ROLL.

        Parameters
        ----------
        angle : float
        """
        self.prepare_roll_motion()

        self.set_position_mode_roll()
        self.set_roll_direction(0)
        self.set_roll_position(angle)

        time.sleep(0.02)
        self.set_roll_direction(4) # trigger modo posição

    def move_all(self, angle):
        """
        Move ambos eixos.

        Parameters
        ----------
        angle : float
        """
        self.prepare_all_motion()

        self.set_position_mode_yaw()
        self.set_position_mode_roll()

        self.set_yaw_direction(0)
        self.set_roll_direction(0)

        self.set_yaw_position(angle)
        self.set_roll_position(angle)

        time.sleep(0.02)
        self.set_yaw_direction(4) # trigger modo posição
        self.set_roll_direction(4) # trigger modo posição

    # =====================================================
    # STOP
    # =====================================================

    def stop_yaw(self):
        """
        Para YAW.

        Parameters
        ----------
        None
        """
        self.set_yaw_direction(0) # trigger stop

    def stop_roll(self):
        """
        Para ROLL.

        Parameters
        ----------
        None
        """
        self.set_roll_direction(0) # trigger stop

    def stop_all(self):
        """
        Para ambos eixos.

        Parameters
        ----------
        None
        """
        self.stop_yaw() # trigger stop yaw
        self.stop_roll() # trigger stop roll

    # =====================================================
    # EMERGENCY
    # =====================================================

    def emergency_stop(self, addr=20):
        """
        Parada de emergência.

        Parameters
        ----------
        addr : int
        """
        self.write(addr, 4)
        time.sleep(0.2)
        self.write(addr, 0)

    def reset_emergency(self, addr=20):
        """
        Reset emergência.

        Parameters
        ----------
        addr : int
        """
        self.write(addr, 1)
        time.sleep(0.2)
        self.write(addr, 0)

    # =====================================================
    # FEEDBACK
    # =====================================================

    def get_pos_yaw(self, addr=0):
        """
        Lê posição YAW.

        Parameters
        ----------
        addr : int : Em graus, convertido de valor 32 bits (2 registradores) usando escala valor / 1_000_000

        rr = self.client.read_input_registers(address=0, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        Lê os registradores de entrada para o eixo YAW, combinando os valores de dois registradores (MSB e LSB) 
        para formar um valor de 32 bits. A conversão para um valor com sinal é feita usando a função to_int32, e
        o resultado é escalado para graus dividindo por 1_000_000. Se a leitura falhar, retorna None.

        Returns
        -------
        float : Posição YAW em graus, ou None em caso de erro.
        """
        rr = self.client.read_input_registers(address=0, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        pos_yaw = self.to_int32(raw) / 1_000_000
        return None if raw is None else pos_yaw

    def get_pos_roll(self, addr=4):
        """
        Lê posição ROLL.

        Parameters
        ----------
        addr : int : Em graus, convertido de valor 32 bits (2 registradores) usando escala valor / 1_000_000

        rr = self.client.read_input_registers(address=4, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        Lê os registradores de entrada para o eixo ROLL, combinando os valores de dois registradores (MSB e LSB) 
        para formar um valor de 32 bits. A conversão para um valor com sinal é feita usando a função to_int32, e
        o resultado é escalado para graus dividindo por 1_000_000. Se a leitura falhar, retorna None.
        
        Returns
        -------
        float : Posição ROLL em graus, ou None em caso de erro.
        """
        rr = self.client.read_input_registers(address=4, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        pos_roll = self.to_int32(raw) / 1_000_000
        return None if raw is None else pos_roll

    def get_pos_all(self, addr_yaw=0, addr_roll=4):

        """
        Lê simultaneamente as posições dos eixos YAW e ROLL.

        Parameters
        ----------
        addr_yaw : int
            Endereço base (LSB) do eixo YAW.
        addr_roll : int
            Endereço base (LSB) do eixo ROLL.

        Returns
        -------
        tuple
            (yaw, roll) em graus.

        Notes
        -----
        - Cada eixo é lido como valor de 32 bits (2 registradores).
        - Conversão aplicada: valor / 1_000_000.
        - Em caso de erro, retorna None no respectivo eixo.
        """
        yaw = self.get_pos_yaw(addr_yaw)
        roll = self.get_pos_roll(addr_roll)
        return yaw, roll
    
    def get_vel_yaw(self, addr=2):
        """
        Lê velocidade YAW.

        Parameters
        ----------
        addr : int : Em °/s, convertido de valor 32 bits (2 registradores) usando escala valor / 1000_1000

        rr = self.client.read_input_registers(address=2, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        Lê os registradores de entrada para o eixo YAW, combinando os valores de dois registradores (MSB e LSB) 
        para formar um valor de 32 bits. A conversão para um valor com sinal é feita usando a função to_int32, e
        o resultado é escalado para graus dividindo por 1_000_000. Se a leitura falhar, retorna None.

        Returns
        -------
        float : Velocidade YAW em °/s, ou None em caso de erro.
        """
        rr = self.client.read_input_registers(address=2, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        vel_yaw = self.to_int32(raw) / 1_000_000
        return None if raw is None else vel_yaw

    def get_vel_roll(self, addr=6):
        """
        Lê velocidade ROLL.

        Parameters
        ----------
        addr : int : Em °/s, convertido de valor 32 bits (2 registradores) usando escala valor / 1000_000

        rr = self.client.read_input_registers(address=6, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        Lê os registradores de entrada para o eixo ROLL, combinando os valores de dois registradores (MSB e LSB) 
        para formar um valor de 32 bits. A conversão para um valor com sinal é feita usando a função to_int32, e
        o resultado é escalado para graus dividindo por 1_000_000. Se a leitura falhar, retorna None.
        
        Returns
        -------
        float : Velocidade ROLL em °/s, ou None em caso de erro.
        """
        rr = self.client.read_input_registers(address=6, count=2)
        raw = (rr.registers[1] << 16) | rr.registers[0]
        vel_roll = self.to_int32(raw) / 1_000_000
        return None if raw is None else vel_roll

    def get_vel_all(self, addr_yaw=2, addr_roll=6):

        """
        Lê simultaneamente as velocidades dos eixos YAW e ROLL.

        Parameters
        ----------
        addr_yaw : int
            Endereço base (LSB) do eixo YAW.
        addr_roll : int
            Endereço base (LSB) do eixo ROLL.

        Returns
        -------
        tuple
            (vel_yaw, vel_roll) em °/s.

        Notes
        -----
        - Cada eixo é lido como valor de 32 bits (2 registradores).
        - Conversão aplicada: valor / 100.
        - Em caso de erro, retorna None no respectivo eixo.
        """
        vel_yaw = self.get_vel_yaw(addr_yaw)
        vel_roll = self.get_vel_roll(addr_roll)
        return vel_yaw, vel_roll
    
'''




from pymodbus.client import ModbusTcpClient
import time
import json


SERVER_PROD = "192.168.1.1"
MODBUS_PORT_PROD = 502

SERVER_TEST = "127.0.0.1"
MODBUS_PORT_TEST = 5020

CONFIG_FILE = "mesa_config.json"


class RotTableWrapper:
    """
    =============================================================================
    RotTableWrapper — Interface de Controle de Mesa Inercial (YAW / ROLL)
    =============================================================================

    DESCRIÇÃO GERAL
    ------------------------------------------------------------------------------------
    Esta classe encapsula (wrapper) o controle de uma mesa inercial de dois eixos (YAW e
    ROLL) através do protocolo Modbus TCP.

    O controlador utiliza registradores de 16 bits com suporte a valores de
    32 bits (DWORD) distribuídos em dois registradores consecutivos (LSB/MSB).

    A interface implementa três camadas:

        NÍVEL 1 — CORE MODBUS
            - write
            - write_dword
            - read_input
            - read_dword

        NÍVEL 2 — UTILITÁRIOS / CONFIGURAÇÃO
            - normalização
            - clipping
            - configuração persistente

        NÍVEL 3 — CONTROLE DE MOVIMENTO
            - prepare_*
            - move_*
            - jog_*
            - stop_*
            - get_*

    ---------------------------------------------------------------------------
    ESCALAS DO SISTEMA
    ---------------------------------------------------------------------------

    Escrita:
        - Velocidade → valor * 100
        - Posição    → valor * 1000

    Leitura:
        - Posição    → valor / 1_000_000
        - Velocidade → valor / 1_000_000

    ---------------------------------------------------------------------------
    MAPA DE REGISTRADORES (RESUMO)
    ---------------------------------------------------------------------------

    YAW:
        24 → modo/habilitação
        28 → trigger/comando
        56 → velocidade (DWORD)
        70 → posição (DWORD)

    ROLL:
        22 → modo/habilitação
        26 → trigger/comando
        46 → velocidade (DWORD)
        60 → posição (DWORD)

    FEEDBACK:
        0-1 → posição YAW (DWORD)
        2-3 → velocidade YAW (DWORD)
        4-5 → posição ROLL (DWORD)
        6-7 → velocidade ROLL (DWORD)

    CONTROLE GLOBAL:
        20 → comandos especiais (apply config / emergency)

    ---------------------------------------------------------------------------
    FLUXO DE COMANDOS (OBRIGATÓRIO)
    ---------------------------------------------------------------------------

    MOVE:
        prepare → mode → write position → delay → trigger

    JOG:
        prepare → write velocity → direction

    STOP:
        write(direction=0)

    READ:
        read → combine → convert → return

    ---------------------------------------------------------------------------
    OBSERVAÇÕES CRÍTICAS
    ---------------------------------------------------------------------------

    - Delays de 0.1 s são OBRIGATÓRIOS na preparação
    - Delay de 0.02 s é OBRIGATÓRIO antes do trigger de posição
    - Ordem de escrita influencia diretamente o comportamento
    - Escrita de DWORD deve respeitar ordem LSB → MSB
    - Sistema não valida automaticamente consistência de estados

    =============================================================================
    """

    def __init__(self, host=SERVER_PROD, port=MODBUS_PORT_PROD):
        """
        Inicializa o cliente Modbus TCP e configura o estado inicial da mesa inercial.

        Este método executa as seguintes etapas:

        --------------------------------------------------------------------
        1. CRIAÇÃO DO CLIENTE MODBUS
        --------------------------------------------------------------------
        Instancia um cliente Modbus TCP usando pymodbus, apontando para
        o endereço IP e porta definidos.

        Não estabelece conexão automaticamente — isso deve ser feito via connect().

        --------------------------------------------------------------------
        2. INICIALIZAÇÃO DAS CONFIGURAÇÕES INTERNAS
        --------------------------------------------------------------------
        Define os parâmetros padrão de operação da mesa inercial:

        - Aceleração (YAW / ROLL)
        - Aceleração máxima
        - Velocidade de movimento
        - Velocidade máxima

        Esses valores são mantidos como atributos públicos e podem ser:

        - Alterados diretamente
        - Modificados via métodos set_*
        - Persistidos em arquivo JSON

        --------------------------------------------------------------------
        3. FATOR DE ESCALA
        --------------------------------------------------------------------
        FACTOR = 100

        Usado para conversão de unidades entre o sistema de alto nível (graus)
        e os registradores Modbus do controlador.

        Exemplo:
            10.5 °/s → 1050 no registrador

        --------------------------------------------------------------------
        4. INTERAÇÃO COM O USUÁRIO (CONFIGURAÇÃO INICIAL)
        --------------------------------------------------------------------

        Durante a inicialização, o usuário é consultado via terminal:

        PASSO 1 — Salvar configuração padrão em arquivo JSON
            Pergunta:
                "Deseja salvar a configuração padrão da mesa no arquivo mesa_config.json? (s/N)"

            Se 's':
                → save_configToFile()

        PASSO 2 — Exibir configuração atual
            Mostra todos os parâmetros configurados no objeto

        PASSO 3 — Aplicar configuração na mesa física
            Pergunta:
                "Deseja enviar a configuração atual para a mesa? (s/N)"

            Se 's':
                → apply_configToTable()

        --------------------------------------------------------------------
        5. OBSERVAÇÕES IMPORTANTES
        --------------------------------------------------------------------
        - O método ensure() é chamado internamente para garantir que a conexão Modbus 
          esteja ativa antes de qualquer operação de leitura ou escrita. Assim, não é
          preciso chamar o método connect() explicitamente antes de executar qualquer
          método de comando para a mesa.
        - A interação usa input() → comportamento bloqueante
        - Ideal para modo CLI / testes manuais
        - NÃO recomendado para aplicações automatizadas ou GUIs
        - Em produção, recomenda-se remover ou parametrizar esse comportamento

        --------------------------------------------------------------------
        Parameters
        ----------
        host : str
            Endereço IP do controlador Modbus TCP.

        port : int
            Porta TCP do serviço Modbus.

        --------------------------------------------------------------------
        Attributes criados
        -----------------
        client : ModbusTcpClient
            Cliente Modbus

        # MAPA INTERNO (SAÍDA DE DADOS MODBUS)
        self._ADDR_YAW_POS  = 0
        self._ADDR_YAW_VEL  = 2
        self._ADDR_ROLL_POS = 4
        self._ADDR_ROLL_VEL = 6

        FACTOR : int
            Fator de escala

        yaw_acceleration_value : int
        roll_acceleration_value : int
        yaw_max_acceleration_value : int
        roll_max_acceleration_value : int
        yaw_move_velocity_value : int
        roll_move_velocity_value : int
        yaw_move_max_velocity_value : int
        roll_move_max_velocity_value : int
        """

        # =========================
        # CLIENT MODBUS
        # =========================
        self.client = ModbusTcpClient(host=host, port=port)

        # =========================
        # ESCALA
        # =========================
        self.FACTOR = 100

        # =========================
        # CONFIGURAÇÃO PADRÃO
        # =========================
        self.yaw_acceleration_value = int(100.0)
        self.roll_acceleration_value = int(100.0)

        self.yaw_max_acceleration_value = int(100.0)
        self.roll_max_acceleration_value = int(100.0)

        self.yaw_move_velocity_value = int(30.0)
        self.roll_move_velocity_value = int(30.0)

        self.yaw_move_max_velocity_value = int(500.0)
        self.roll_move_max_velocity_value = int(200.0)

        # MAPA INTERNO (SAÍDA DE DADOS MODBUS)
        self._ADDR_YAW_POS  = 0
        self._ADDR_YAW_VEL  = 2
        self._ADDR_ROLL_POS = 4
        self._ADDR_ROLL_VEL = 6

        # =====================================================
        # INTERAÇÃO: SALVAR CONFIG
        # =====================================================
        print("Deseja salvar a configuração padrão da mesa no arquivo mesa_config.json? (s/N)")
        choice = input().strip().lower()

        if choice == "":
            choice = "n"

        if choice == "s":
            self.save_configToFile()

        # =====================================================
        # EXIBE CONFIGURAÇÃO ATUAL
        # =====================================================

        print("Deseja ver a configuração padrão da mesa? (s/N)")
        choice = input().strip().lower()
        if choice == "":
            choice = "n"
        if choice == "s":
            print("\nCONFIGURAÇÃO ATUAL DA MESA INERCIAL")
            print(f"YAW_ACC={self.yaw_acceleration_value:.2f} °/s²")
            print(f"ROLL_ACC={self.roll_acceleration_value:.2f} °/s²")
            print(f"YAW_MAX_ACC={self.yaw_max_acceleration_value:.2f} °/s²")
            print(f"ROLL_MAX_ACC={self.roll_max_acceleration_value:.2f} °/s²")
            print(f"YAW_MOVE_VEL={self.yaw_move_velocity_value:.2f} °/s")
            print(f"ROLL_MOVE_VEL={self.roll_move_velocity_value:.2f} °/s")
            print(f"YAW_MAX_VEL={self.yaw_move_max_velocity_value:.2f} °/s")
            print(f"ROLL_MAX_VEL={self.roll_move_max_velocity_value:.2f} °/s")

        # =====================================================
        # INTERAÇÃO: APLICAR CONFIG
        # =====================================================
        print("\nDeseja enviar a configuração atual para a mesa? (s/N)")
        choice = input().strip().lower()

        if choice == "":
            choice = "n"

        if choice == "s":
            self.apply_configToTable()

    # =====================================================
    # CONNECTION
    # =====================================================

    def connect(self):
        """
        Estabelece conexão TCP com o servidor Modbus.

        Returns
        -------
        bool
            True se a conexão foi estabelecida com sucesso, False caso contrário.

        Observações
        -----------
        - Deve ser chamado antes de qualquer operação Modbus.
        - Em caso de falha, métodos subsequentes podem lançar erro.
        """
        return self.client.connect()

    def close(self):
        """
        Encerra a conexão TCP com o servidor Modbus.

        Observações
        -----------
        - Após chamada, qualquer operação requer nova conexão.
        """
        self.client.close()

    def _ensure(self):
        """
        Garante que a conexão Modbus esteja ativa.

        Comportamento
        -------------
        - Se não estiver conectado, tenta reconectar automaticamente.
        - Não lança exceção diretamente.

        Uso Interno
        -----------
        Chamado por todos os métodos de I/O Modbus.
        """
        if not self.client.connected:
            self.client.connect()

    # =====================================================
    # CORE MODBUS
    # =====================================================

    def write(self, addr, value):
        """
        Escreve um valor em um registrador holding (16 bits).

        Parameters
        ----------
        addr : int
            Endereço do registrador.
        value : int
            Valor inteiro a ser escrito.

        Returns
        -------
        ModbusResponse

        Notas
        -----
        - Valor é convertido para inteiro.
        - Não realiza validação de faixa.
        - Operação síncrona.
        """
        self._ensure()
        return self.client.write_register(addr, int(value))

    def write_dword(self, addr, value):
        """
        Escreve um valor de 32 bits (DWORD) em dois registradores consecutivos.

        Estrutura:
            addr     → LSB
            addr + 1 → MSB

        Parameters
        ----------
        addr : int
            Endereço base (LSB).
        value : int
            Valor inteiro de 32 bits.

        Observações
        -----------
        - Ordem de escrita: LSB → MSB (OBRIGATÓRIO)
        - Não há atomicidade (duas operações separadas)
        """

        value = int(value)
        low = value & 0xFFFF
        high = (value >> 16) & 0xFFFF

        self.write(addr, low)
        self.write(addr + 1, high)

    def read_input(self, addr, count=2):
        """
        Lê registradores de entrada (Input Registers).

        Parameters
        ----------
        addr : int
            Endereço inicial.
        count : int
            Quantidade de registradores a serem lidos.

        Returns
        -------
        ModbusResponse

        Notas
        -----
        - Não realiza parsing automático.
        - Deve ser tratado externamente.
        """
        self._ensure()
        return self.client.read_input_registers(addr, count)

    def read_dword(self, addr):
        """
        Lê um valor de 32 bits a partir de dois registradores.

        Parameters
        ----------
        addr : int
            Endereço base (LSB).

        Returns
        -------
        int or None

        Fluxo
        -----
        read_input → combine → return
        """
        r = self.read_input(addr, 2)
        if r.isError():
            return None
        return (r.registers[1] << 16) | r.registers[0]

    # =====================================================
    # UTILITÁRIOS
    # =====================================================

    def to_int32(self, raw):
        """
        Converte valor de 32 bits sem sinal para inteiro com sinal.

        Parameters
        ----------
        raw : int

        Returns
        -------
        int

        Detalhes
        --------
        - Usa complemento de dois
        - Necessário para interpretar valores negativos vindos do controlador
        """
        return raw - 0x100000000 if raw & 0x80000000 else raw

    def normalize(self, deg):
        """
        Normaliza ângulo para formato esperado pelo controlador.

        Parameters
        ----------
        deg : float

        Returns
        -------
        int

        Regras
        ------
        - Converte para escala interna (*1000)
        - Evita valores negativos usando espelhamento
        """
        v = int(deg * 1000)
        return 360000 - abs(v) if v < 0 else v

    def _read_int32(self, addr):
        """
        Lê um valor de 32 bits (2 registradores Modbus) e converte para inteiro com sinal.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Executa uma leitura de 2 registradores consecutivos (16 bits cada),
        combinando-os em um valor de 32 bits no formato:

            raw = (MSB << 16) | LSB

        Em seguida, converte o valor para inteiro com sinal utilizando
        representação em complemento de dois.

        --------------------------------------------------------------------
        PARÂMETROS
        --------------------------------------------------------------------
        addr : int
            Endereço base (LSB) do valor 32 bits.

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        int | None
            Valor convertido (com sinal), ou None em caso de erro de leitura.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Esta função NÃO aplica escala (ex: divisão por 1_000_000)
        - Deve ser usada como primitiva interna (Layer 2)
        - Centraliza a lógica de parsing Modbus → reduz duplicação
        """

        rr = self.read_input(addr, 2)

        if rr.isError():
            return None

        raw = (rr.registers[1] << 16) | rr.registers[0]
        return self.to_int32(raw)

    # =====================================================
    # CONFIGURAÇÃO E PERSISTÊNCIA
    # =====================================================

    def set_config(self):
        """
        Aplica configuração completa ao controlador e persiste em arquivo.

        Fluxo:
            apply_configToTable → save_configToFile

        Observações
        -----------
        - Deve ser chamado após alteração de parâmetros internos
        """
        self.apply_configToTable()
        self.save_configToFile()

    def apply_configToTable(self):
        """
        Escreve parâmetros de movimento nos registradores e aplica configuração.

        Registradores utilizados
        ------------------------
        YAW:
            50, 52, 72, 90

        ROLL:
            40, 42, 62, 80

        Controle:
            20 → comando apply

        Sequência
        ---------
        write parâmetros → trigger apply → delay → reset
        """

        self.write(50, self.yaw_acceleration_value * self.FACTOR)
        self.write(52, self.yaw_max_acceleration_value * self.FACTOR)
        self.write(72, self.yaw_move_velocity_value * self.FACTOR)
        self.write(90, self.yaw_move_max_velocity_value * self.FACTOR)

        self.write(40, self.roll_acceleration_value * self.FACTOR)
        self.write(42, self.roll_max_acceleration_value * self.FACTOR)
        self.write(62, self.roll_move_velocity_value * self.FACTOR)
        self.write(80, self.roll_move_max_velocity_value * self.FACTOR)

        self.write(20, 2)
        time.sleep(1)
        self.write(20, 0)

    def save_configToFile(self):
        """
        Persiste configuração atual em arquivo JSON.

        Estrutura
        ---------
        Inclui:
            - parâmetros de posição
            - aceleração
            - velocidade máxima

        Caminho
        -------
        CONFIG_FILE

        Observações
        -----------
        - Sobrescreve arquivo existente
        - Não valida permissões
        """

        data = {
            "velPosAzimute": self.yaw_move_velocity_value,
            "velPosTilt": self.roll_move_velocity_value,
            "accPosAzimute": self.yaw_acceleration_value,
            "accPosTilt": self.roll_acceleration_value,
            "maxVelAzimute": self.yaw_move_max_velocity_value,
            "maxVelTilt": self.roll_move_max_velocity_value,
            "maxAccAzimute": self.yaw_max_acceleration_value,
            "maxAccTilt": self.roll_max_acceleration_value
        }

        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    # =====================================================
    # PREPARAÇÃO PARA MOVIMENTO
    # =====================================================

    def prepare_yaw_motion(self):
        """
        Prepara eixo YAW para movimento.

        Sequência obrigatória:
            write(acc)
            write(max_acc)
            enable roll
            delay 0.1
            enable yaw
            delay 0.1
        """

        self.write(40, self.yaw_acceleration_value)
        self.write(42, self.yaw_max_acceleration_value)

        self.write(22, 1)
        time.sleep(0.1)

        self.write(24, 1)
        time.sleep(0.1)

    def prepare_roll_motion(self):
        """
        Prepara eixo ROLL para movimento.

        Mesma lógica de dependência do YAW.
        """

        self.write(50, self.roll_acceleration_value)
        self.write(52, self.roll_max_acceleration_value)

        self.write(22, 1)
        time.sleep(0.1)

        self.write(24, 1)
        time.sleep(0.1)

    def prepare_all_motion(self):
        """
        Prepara ambos os eixos sequencialmente.

        Ordem:
            YAW → ROLL
        """
        self.prepare_yaw_motion()
        self.prepare_roll_motion()

    # =====================================================
    # JOG - VELOCIDADE CONTÍNUA
    # =====================================================

    def jog_yaw(self, vel):
        """
        Executa movimento contínuo (modo JOG) no eixo YAW.

        Parameters
        ----------
        vel : float
            Velocidade em °/s * 100 (FACTOR)

        Sequência:
            prepare → write velocity → trigger direction

        Registradores:
            56 → velocidade
            28 → direção e trigger (1=positivo, 2=negativo, 0=stop)
        """

        self.prepare_yaw_motion()
        self.write(56, abs(int(vel * self.FACTOR)))

        self.write(28, 1 if vel > 0 else 2 if vel < 0 else 0)

    def jog_roll(self, vel):
        """
        Executa movimento contínuo (modo JOG) no eixo ROLL.

        Parameters
        ----------
        vel : float
            Velocidade em °/s * 100 (FACTOR)

        Sequência:
            prepare → write velocity → trigger direction

        Registradores:
            46 → velocidade
            26 → direção e trigger (1=positivo, 2=negativo, 0=stop)
        """
        self.prepare_roll_motion()
        self.write(46, abs(int(vel * self.FACTOR)))

        self.write(26, 1 if vel > 0 else 2 if vel < 0 else 0)

    def jog_all(self, vel):
        """
        Movimento contínuo simultâneo YAW + ROLL.

        Parameters
        ----------
        vel : float
            Velocidade em °/s * 100 (FACTOR)
        """
        self.jog_yaw(vel)
        self.jog_roll(vel)

    # =====================================================
    # MOVE - POSICIONAMENTO ABSOLUTO
    # =====================================================

    def move_yaw(self, angle):
        """
        Movimento absoluto YAW.

        Parameters
        ----------
        angle : float
            Posicão em graus
        
        Sequência:
            prepare → mode → stop → write pos → delay → trigger
        """

        self.prepare_yaw_motion()

        self.write(24, 2)
        self.write(28, 0)

        self.write_dword(70, self.normalize(angle))

        time.sleep(0.02)
        self.write(28, 4)

    def move_roll(self, angle):
        """
        Movimento absoluto ROLL.

        Parameters
        ----------
        angle : float
            Posicão em graus
        
        Sequência:
            prepare → mode → stop → write pos → delay → trigger
        """

        self.prepare_roll_motion()

        self.write(22, 2)
        self.write(26, 0)

        self.write_dword(60, self.normalize(angle))

        time.sleep(0.02)
        self.write(26, 4)

    def move_all(self, angle):
        """
        Movimento absoluto simultâneo.

        Importante:
            Ambos os eixos são disparados quase simultaneamente.

        Parameters
        ----------
        angle : float
            Posição em graus
        
        Sequência:
            prepare → mode → stop → write pos → delay → trigger
        """

        self.prepare_all_motion()

        self.write(24, 2)
        self.write(22, 2)

        self.write(28, 0)
        self.write(26, 0)

        self.write_dword(70, self.normalize(angle))
        self.write_dword(60, self.normalize(angle))

        time.sleep(0.02)

        self.write(28, 4)
        self.write(26, 4)

    # =====================================================
    # STOP
    # =====================================================

    def stop_yaw(self):
        """
        Para imediatamente o eixo YAW.

        Método atua apenas zerando o registrador de direção.
        """
        self.write(28, 0)

    def stop_roll(self):
        """
        Para eixo ROLL.
        """
        self.write(26, 0)

    def stop_all(self):
        """
        Para ambos os eixos simultaneamente.
        """
        self.stop_yaw()
        self.stop_roll()

    # =====================================================
    # FEEDBACK — POSIÇÃO
    # =====================================================

    def get_pos_yaw(self):
        """
        Retorna a posição do eixo YAW em graus.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Lê o valor bruto de posição do eixo YAW (32 bits) a partir do mapa
        interno de registradores e converte para unidade física (graus).

        Conversão aplicada:
            posição = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Posição YAW em graus, ou None em caso de erro.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Não expõe endereços Modbus
        - Usa função interna _read_int32()
        - Conversão com sinal preservada
        """

        v = self._read_int32(self._ADDR_YAW_POS)
        return None if v is None else v / 1_000_000

    def get_pos_roll(self):
        """
        Retorna a posição do eixo ROLL em graus.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Equivalente ao método get_pos_yaw(), aplicado ao eixo ROLL.

        Conversão aplicada:
            posição = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Posição ROLL em graus, ou None em caso de erro.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Mantém simetria com eixo YAW
        """

        v = self._read_int32(self._ADDR_ROLL_POS)
        return None if v is None else v / 1_000_000

    def get_pos_all(self):
        """
        Retorna simultaneamente as posições dos eixos YAW e ROLL.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Executa duas leituras independentes:

            YAW  → get_pos_yaw()
            ROLL → get_pos_roll()

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        tuple
            (yaw, roll) em graus

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Não é uma leitura atômica (duas requisições Modbus)
        - Pode haver pequeno desvio temporal entre eixos
        """

        return (
            self.get_pos_yaw(),
            self.get_pos_roll()
        )

    # =====================================================
    # FEEDBACK — VELOCIDADE
    # =====================================================

    def get_vel_yaw(self):
        """
        Retorna a velocidade do eixo YAW em graus por segundo (°/s).

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Lê o valor bruto de velocidade (32 bits) do eixo YAW e aplica
        conversão para unidade física.

        Conversão:
            velocidade = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Velocidade YAW em °/s, ou None em caso de erro.

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Sinal indica direção do movimento
        - Valor zero indica eixo parado
        """
        v = self._read_int32(self._ADDR_YAW_VEL)
        return None if v is None else v / 1_000_000

    def get_vel_roll(self):
        """
        Retorna a velocidade do eixo ROLL em graus por segundo (°/s).

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Equivalente ao método get_vel_yaw(), aplicado ao eixo ROLL.

        Conversão:
            velocidade = valor_bruto / 1_000_000

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        float | None
            Velocidade ROLL em °/s, ou None em caso de erro.
        """

        v = self._read_int32(self._ADDR_ROLL_VEL)
        return None if v is None else v / 1_000_000

    def get_vel_all(self):
        """
        Retorna simultaneamente as velocidades dos eixos YAW e ROLL.

        --------------------------------------------------------------------
        DESCRIÇÃO
        --------------------------------------------------------------------
        Executa duas leituras independentes:

            YAW  → get_vel_yaw()
            ROLL → get_vel_roll()

        --------------------------------------------------------------------
        RETORNO
        --------------------------------------------------------------------
        tuple
            (vel_yaw, vel_roll) em °/s

        --------------------------------------------------------------------
        OBSERVAÇÕES
        --------------------------------------------------------------------
        - Não é leitura síncrona
        - Pode haver defasagem temporal entre eixos
        """

        return (
            self.get_vel_yaw(),
            self.get_vel_roll()
        )
        # =====================================================
        # EMERGENCY
        # =====================================================

    def emergency_stop(self):
        """
        Executa parada de emergência via registrador de controle global.

        Sequência:
            write(20, 4) → delay → write(20, 0)
        """
        self.write(20, 4)
        time.sleep(0.2)
        self.write(20, 0)

    def emergency_reset(self):
        """
        Reseta estado de emergência do sistema.

        Sequência:
            write(20, 1) → delay → write(20, 0)
        """
        self.write(20, 1)
        time.sleep(0.2)
        self.write(20, 0)