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

Dentro do script, utilizar a classe:

~~~python
from rotatorytable import RotTableWrapper

rot = RotTableWrapper() # sem argumentos no construtor, usa-se o padrão, que é 127.0.0.1:5020. Veja na classe.

rot.enable()

rot.posazi(30)
rot.postilt(10)
rot.pos(230.3) # ambos eixos

rot.jogazi(20)
rot.jogtilt(33.1)
rot.stop()
rot.jog(22.2) # ambos eixos

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

rot = RotTableWrapper() # sem argumentos no construtor, usa-se o padrão, que é 127.0.0.1:5020. Veja na classe.

rot.enable()

rot.posazi(45.4)
rot.postitl(-10.4)
rot.pos(22.9) # ambos eixos

rot.jogazi(30.0)
rot.jogtilt(60.0)
rot.stop()
rot.jog(22.4) # ambos eixos
rot.stop()
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

# 5. COMPORTAMENTO ESPERADO

- `enable()` → libera controle da mesa
- `pos()` → movimento absoluto de ambos eixos
- `jog()` → movimento contínuo por velocidade em ambos eixos
- `stop()` → parada imediata de ambos eixos
- Simulador reflete estado em tempo real

---

# 6. OBSERVAÇÕES IMPORTANTES

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

# 7. OBJETIVO DO TESTE

Validar:

- comunicação Modbus TCP
- comandos de posição e velocidade
- comportamento do simulador
- integração da classe `RotTableWrapper`

---