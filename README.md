# RotTableWrapper (RotTableComm refatorada) — Classe de Controle da Mesa Inercial (Python 3.12.3, pymodbus 3.7.4)

Autor: Roney D. Silva e equipe EFO-S  

---

## 1. Visão Geral

A classe `RotTableWrapper` fornece uma interface de alto nível para controle de uma mesa inercial de dois eixos (**Yaw** e **Roll**) via protocolo **Modbus TCP**.

Ela encapsula:

- Controle de posição absoluta
- Controle de velocidade (jog)
- Configuração de ganhos e limites
- Conversão de valores 32 bits (INT32 via dois registradores 16 bits)
- Normalização de ângulos
- Sequência correta de comandos do controlador da mesa
- Delays obrigatórios (`time.sleep`) para sincronização com o firmware

---

## 2. Dependências

# Windows

- Python 3.12.3
- Observar a versão correta do pacote pymodbus (3.7.4), definida no requirements.txt.
- pip install -r requirements.txt --no-cache

# Linux Mint 22

- Python 3.12.3
- Observar a versão correta do pacote pymodbus (3.7.4), definida no requirements.txt.
- pip install -r requirements.txt --break-system-packages --no-cache


## 3. Conceitos Importantes

### 3.1 Registradores INT32 (2x16 bits)

O controlador da mesa utiliza registradores de 16 bits.  
Valores maiores (posição) são armazenados em 32 bits:

- valor (32 bits) = HIGH << 16 | LOW  (modbus é um protocolo de 16 bits)

---

### 3.2 Escalas

| Parâmetro  | Escala |
|------------|--------|
| Posição    | ×1000  |
| Velocidade | ×100   | 

Obs.:
Para a velocidade, 16 bits é suficiente porque o maior valor de velocidade será 500 °/s (500 x 100) que é 
menor que 65535

---

### 3.3 Normalização de Ângulo

Todos os ângulos são convertidos para o intervalo:

~~~
[0, 360000]
~~~

Função:

~~~
normalize(angle):
    angle = angle * 1000
    if angle < 0:
        angle = 360000 - abs(angle)
    return angle
~~~

---

## 4. Registradores do Controlador da Mesa

### Input Registers (Leitura)

| Addr | Eixo   | Descrição |
|------|--------|----------|
| 0-1  | Yaw | Posição |
| 2-3  | Yaw | Velocidade |
| 4-5  | Roll    | Posição |
| 6-7  | Roll    | Velocidade |

---

### Holding Registers (Controle)

| Addr | Função | Observação |             
|------|--------|------------|
| 22   | Enable Roll |
| 24   | Enable Yaw |
| 26   | CMD Roll |
| 28   | CMD Yaw |
| 40   | Acc Roll |
| 42   | Max Acc Roll |
| 50   | Acc Yaw |
| 52   | Max Acc Yaw |
| 46-47| Vel Roll |    * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador (46) |
| 56-57| Vel Yaw |     * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador (56) |
| 60-61| Target Roll |     * Para o valor do target (posição angular de roll), 2 registradores de 16 bits são usados | 
| 70-71| Target Yaw |  * Para o valor do target (posição angular de yaw), 2 registradores de 16 bits são usados | 
| 80   | MaxVelRoll |      * Roll max velocity |
| 82   | MaxAccRoll |      * Roll max acceleration |
| 90   | MaxVelYaw |       * Yaw max velocity |
| 92   | MaxAccYaw |       * Yaw max acceleration |
---

## 5. Arquivo rotatorytable.py Refatorado

~~~
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
'
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
        self.yaw_move_velocity_value = int(77.0) # °/s
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
                    
~~~

---

## 7. Observações de Engenharia

- `time.sleep(0.02)` é obrigatório para sincronização do controlador da mesa
- Registradores devem ser escritos na ordem correta:
  1. Enable
  2. Reset comando
  3. Escrita de posição/velocidade
  4. Start comando
- Yaw e Roll são independentes, mas compartilham o mesmo barramento lógico
- Falha em sequência pode gerar comportamento indeterminado no movimento

---

## 8. Ponto Crítico

O controlador da mesa NÃO aceita diretamente valores fora da escala:

- Posicionamento: sempre ×1000
- Velocidade: sempre ×100
- INT32 deve ser sempre dividido em LOW/HIGH

---

## 9. Extensões Futuras

- Retry automático Modbus
- Execução de scripts de movimento

# 👥 Equipe
**Roney e EFO-S**