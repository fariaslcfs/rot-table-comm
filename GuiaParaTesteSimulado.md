# GuiaParaTesteSimulado.md  
## Guia de Teste — Simulador da Mesa Inercial (IEAv)

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

Criar um arquivo de teste, por exemplo:

~~~
test_rot.py
~~~

E executar:

~~~
python test_rot.py
~~~

Dentro do script, utilizar a classe:

~~~python
from rotatorytable import RotTableWrapper

rot = RotTableWrapper("127.0.0.1", 5020)

rot.connect()
rot.enable()

rot.pos("azimuth", 30)
rot.pos("tilt", 10)

rot.jog("azimuth", 20)
rot.stop()

rot.close()
~~~

---

## 3.2 MODO INTERPRETADOR (REPL)

Abrir o Python diretamente:

~~~
python
~~~

Importar e executar comandos manualmente:

~~~python
from rotatorytable import RotTableWrapper

rot = RotTableWrapper("127.0.0.1", 5020)
rot.connect()
rot.enable()

rot.pos("azimuth", 45)
rot.jog("tilt", -10)

rot.stop()
rot.close()
~~~

---

# 4. FLUXO COMPLETO DE TESTE (RECOMENDADO)

Ordem ideal:

1. Iniciar simulador (`simuladormesacomcomandos.py`)
2. (Opcional) Iniciar interface web (`interfacemesainercial.py`)
3. Executar script Python ou REPL
4. Enviar comandos de movimento
5. Observar resposta no simulador

---

# 5. COMPORTAMENTO ESPERADO

- `enable()` → libera controle da mesa
- `pos()` → movimento absoluto com rampa
- `jog()` → movimento contínuo por velocidade
- `stop()` → parada imediata
- Simulador reflete estado em tempo real

---

# 6. OBSERVAÇÕES IMPORTANTES

- O simulador substitui o hardware real da mesa
- O arquivo `mesa_config.json` define o estado inicial
- Sempre garantir que o simulador esteja rodando antes dos testes
- Portas padrão:
  - Simulador: `5020`
  - Mesa real: `502`

---

# 7. OBJETIVO DO TESTE

Validar:

- comunicação Modbus TCP
- comandos de posição e velocidade
- comportamento do simulador
- integração da classe `RotTableWrapper`

---