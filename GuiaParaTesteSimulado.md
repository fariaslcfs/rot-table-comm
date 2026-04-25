# GuiaParaTesteSimulado.md  
## Guia de Teste — Simulador da Mesa Inercial (EFO-S)

> Este documento descreve o procedimento padrão para testar a classe `RotTableWrapper`, localizada em `rotatorytable.py`, utilizando o simulador da mesa inercial (`simuladormesacomcomandos.py`) e a interface web (`interfacemesainercial.py`).

---

# 1. INICIAR O SIMULADOR DA MESA

Execute no terminal:

~~~
python simuladormesacomcomandos.py
~~~

Durante a inicialização, será exibido um menu interativo.

## Opções principais:

- **J ou j**
  - Inicia o simulador utilizando o arquivo:
    - `mesa_config.json`
  - Modo recomendado para testes padrão.

- **I ou i**
  - Permite ajustar manualmente os parâmetros da mesa:
    - posição inicial
    - velocidade
    - aceleração
    - constantes de simulação

> ⚠️ Observação: o simulador deve permanecer ativo durante todos os testes.

---

# 2. INICIAR A INTERFACE WEB (OPCIONAL)

Em outro terminal, execute:

~~~
python interfacemesainercial.py
~~~

Esta interface permite:
- monitoramento em tempo real
- envio de comandos via HTTP
- visualização de posição e velocidade

> Pode ser usada em paralelo ao simulador.

---

# 3. EXECUTAR TESTES COM PYTHON

Existem duas formas recomendadas:

---

## 3.1 MODO SCRIPT (.py)

Usar o arquivo example.py:

E executar:

~~~
python example.py
~~~

---

## 3.2 MODO INTERPRETADOR (REPL)

REPL (Read-Eval-Print Loop), ou seja, dentro do Python (linha de comandos do intepretador interativo do Python):

Abrir o Python diretamente:

~~~
python
~~~

Importar e executar comandos manualmente:

~~~python
from rotatorytable import RotTableWrapper

rot = RotTableWrapper("127.0.0.1", 5020)

rot.move_yaw(45)

rot.get_pos_yaw()

rot.move_roll(30)

rot.get_pos_roll()

rot.move_yaw(0)

rot.move_roll(0)

rot.get_pos_yaw()

rot.get_pos_roll()

rot.jog_yaw(20)

rot.get_vel_yaw()

rot.stop_yaw()

rot.get_vel_yaw()

rot.jog_roll(-15)

rot.get_vel_roll()

rot.stop_roll()

rot.get_vel_roll()

rot.jog_yaw(-30)

rot.get_vel_yaw()

rot.jog_roll(0)

rot.jog_roll(20)

rot.get_vel_roll()

rot.stop_all()

rot.get_vel_yaw()

rot.get_vel_roll()

rot.jog_all(10)

rot.get_vel_yaw()

rot.get_vel_roll()

rot.stop_all()

rot.get_vel_yaw()

rot.get_vel_roll()

rot.jog_all(90.0)

rot.get_vel_all()

rot.stop_all()

rot.get_vel_yaw()

rot.get_vel_roll()

rot.move_all(0)

rot.get_pos_yaw()

rot.get_pos_roll()

rot.jog_all(10)

rot.stop_all()

rot.mov_all(0)

rot.emergency_stop()

rot.emergency_reset()

rot.move_all(180)

rot.move_all(0)

rot.close()

~~~

---

# 4. FLUXO COMPLETO DE TESTE (RECOMENDADO)

Ordem ideal:

1. Iniciar simulador (`simuladormesacomcomandos.py`)
2. (Indicado se quiser ver a simulação) Iniciar interface web (`interfacemesainercial.py`)
3. Executar script Python ou REPL (Executar os comandos no interpretador)
4. Enviar comandos de movimento
5. Observar resposta no simulador

---


# 5. OBSERVAÇÕES IMPORTANTES

- O simulador substitui o hardware real da mesa
- O arquivo `mesa_config.json` define o estado inicial
- Sempre garantir que o simulador esteja rodando antes dos testes
- IP mesa:
  - Simulador: `127.0.0.1`
  - Mesa real: `192.168.1.1`

- Portas padrão:
  - Simulador: `5020`
  - Mesa real: `502`

---

# 6. OBJETIVO DO TESTE

Validar:

- comunicação Modbus TCP
- comandos de posição e velocidade
- comportamento do simulador
- integração da classe `RotTableWrapper`

---