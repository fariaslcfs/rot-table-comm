# RotTableComm — Guia Rápido (Cheat Sheet)

> Controle da mesa inercial IEAv (Azimuth + Tilt) via Modbus TCP  
> Uso direto para testes e scripts simples

---

# 1. INICIALIZAÇÃO

~~~
RotTableComm(host="127.0.0.1", port=5020)
~~~

Cria interface com a mesa ou simulador.

---

# 2. CONEXÃO

~~~
connect()
~~~
Abre comunicação Modbus TCP.

~~~
close()
~~~
Encerra comunicação.

---

# 3. HABILITAR / PARAR

~~~
enable()
~~~
Ativa Azimuth + Tilt.

~~~
disable()
~~~
Desativa sistema.

~~~
stop()
~~~
Para todos os movimentos imediatamente.

---

# 4. POSIÇÃO (ABSOLUTA)

~~~
pos("azimuth", angulo)
pos("tilt", angulo)
pos("both", angulo)
~~~

Exemplo:
- pos("azimuth", 45) → move Azimuth para 45°
- pos("tilt", 10) → move Tilt para 10°

---

# 5. JOG (VELOCIDADE)

~~~
jog("azimuth", velocidade)
jog("tilt", velocidade)
jog("both", velocidade)
~~~

Exemplo:
- jog("azimuth", 20) → gira Azimuth positivo
- jog("tilt", -15) → gira Tilt negativo

---

# 6. LEITURA (FEEDBACK)

~~~
get_azimuth()
~~~
Retorna posição atual do Azimuth (graus)

~~~
get_tilt()
~~~
Retorna posição atual do Tilt (graus)

---

# 7. REGRAS IMPORTANTES

- Valores de posição: graus
- Velocidade: escala interna ×100
- Controle usa Modbus TCP
- Sempre chamar `enable()` antes de mover
- Usar `stop()` para interromper movimento

---

# 8. EXEMPLO MÍNIMO

~~~
rot = RotTableComm("127.0.0.1", 5020)

rot.connect()
rot.enable()

rot.pos("azimuth", 30)
rot.jog("tilt", 10)

rot.stop()
rot.close()
~~~

---

# 9. RESUMO

| Ação | Função |
|------|--------|
| Habilitar | enable() |
| Parar | stop() |
| Posicionar | pos(axis, angle) |
| Girar | jog(axis, velocity) |
| Ler posição | get_azimuth(), get_tilt() |

---