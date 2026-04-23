# RotTableWrapper (RotTableComm refatorada) — Classe de Controle da Mesa Inercial (Python 3.12.3, pymodbus 3.7.4)

Autor: Roney D. Silva e equipe EFO-S  

---

## 1. Visão Geral

A classe `RotTableWrapper` fornece uma interface de alto nível para controle de uma mesa inercial de dois eixos (**Azimuth** e **Tilt**) via protocolo **Modbus TCP**.

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
Valores maiores (posição/velocidade) são armazenados em 32 bits:

- valor (32 bits) = HIGH << 16 | LOW  (modbus é um protocolo de 16 bits)

---

### 3.2 Escalas

| Parâmetro  | Escala |
|------------|--------|
| Posição    | ×1000  |
| Velocidade | ×100   |

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
| 0-1  | Azimuth | Posição |
| 2-3  | Azimuth | Velocidade |
| 4-5  | Tilt    | Posição |
| 6-7  | Tilt    | Velocidade |

---

### Holding Registers (Controle)

| Addr | Função | Observação |             
|------|--------|------------|
| 22   | Enable Tilt |
| 24   | Enable Azimuth |
| 26   | CMD Tilt |
| 28   | CMD Azimuth |
| 40   | Acc Tilt |
| 42   | Max Acc Tilt |
| 50   | Acc Azimuth |
| 52   | Max Acc Azimuth |
| 46-47| Vel Tilt |        * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador |
| 56-57| Vel Azimuth |     * O valor máximo de velocidade não ultrapassa 65535 (16 bits) usando somente 1 registrador |
| 60-61| Target Tilt |     * Para o valor do target (posição angular de azimute), 2 registradores de 16 bits são usados | 
| 70-71| Target Azimuth |  * Para o valor do target (posição angular de inclinação), 2 registradores de 16 bits são usados | 
| 80   | MaxVelTitl |      * Tilt max velocity |
| 82   | MaxAccTilt |      * Tilt max acceleration |
| 90   | MaxVelAzi |       * Azimuth max velocity |
| 92   | MaxAccAzi |       * Azimuth max acceleration |
---

## 5. Arquivo rotatorytable.py Refatorado

~~~
from pymodbus.client import ModbusTcpClient
import time

SERVER_PROD = "192.168.1.1"    # Mesa real
MODBUS_PORT = 502              # Porta padrão Modbus TCP  
SERVER_TEST = "127.0.0.1"      # Simulador local. Lembre-se de iniciar o simulador antes de executar este script.
MODBUS_PORT_TEST = 5020        # Evita conflito com porta 502 (well-known)

from pymodbus.client import ModbusTcpClient
import time


SERVER_PROD = "192.168.1.1"
MODBUS_PORT_PROD = 502

SERVER_TEST = "127.0.0.1"
MODBUS_PORT_TEST = 5020


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

        write(addr_acc, acc_reg_value)
        write(addr_maxacc, acc_reg_value)

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

        self.max_vel_yaw = 500.0  # °/s 
        self.max_vel_roll = 200.0 # °/s

        self.acc_value = 100.0 # °/s²
        self.max_acc_reg_value = int(self.acc_value * 100)

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
        return max(-self.max_vel_yaw, min(self.max_vel_yaw, vel))

    def clip_vel_roll(self, vel):
        """
        Limita velocidade ROLL. Max = 200.0 °/s

        Parameters
        ----------
        vel : float
        """
        return max(-self.max_vel_roll, min(self.max_vel_roll, vel))

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
        self.write(addr_acc, self.max_acc_reg_value)
        self.write(addr_max_acc, self.max_acc_reg_value)
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
        self.write(addr_acc, self.max_acc_reg_value)
        self.write(addr_max_acc, self.max_acc_reg_value)
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

    def set_yaw_velocity(self, vel, addr_vel=56):
        """
        Define velocidade YAW.

        Parameters
        ----------
        vel : float
        addr_vel : int

        Returns 
        -------
        int : Velocidade aplicada (após clipping e escala)
        """
        v = int(self.clip_vel_yaw(vel) * 100)
        self.write_dword(addr_vel, abs(v))
        return v

    def set_roll_velocity(self, vel, addr_vel=46):
        """
        Define velocidade ROLL.

        Parameters
        ----------
        vel : float
        addr_vel : int

        Returns
        -------
        int : Velocidade aplicada (após clipping e escala)

        """
        v = int(self.clip_vel_roll(vel) * 100)
        self.write_dword(addr_vel, abs(v))
        return v

    def set_yaw_position(self, angle, addr_pos=70):
        """
        Define posição YAW.

        Parameters
        ----------
        angle : float
        addr_pos : int
        """
        self.write_dword(addr_pos, self.normalize(angle))

    def set_roll_position(self, angle, addr_pos=60):
        """
        Define posição ROLL.

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
- Azimuth e Tilt são independentes, mas compartilham o mesmo barramento lógico
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