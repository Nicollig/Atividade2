import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psutil
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from entity.infos import InfoRede, TesteConectividade


# Caminho dos arquivos do projeto
PATH_ATUAL = Path(__file__).resolve().parent
PATH_HTML = PATH_ATUAL.parent / "front-end" / "templates"

templates = Jinja2Templates(directory=str(PATH_HTML))

app = FastAPI(title="Monitor de Rede Local")


def obter_nome_equipamento():
    return socket.gethostname()


def obter_interface_rede():
    interfaces = psutil.net_if_addrs()
    estados = psutil.net_if_stats()

    for nome, enderecos in interfaces.items():

        if nome not in estados:
            continue

        if not estados[nome].isup:
            continue

        for endereco in enderecos:

            if endereco.family == socket.AF_INET:
                return nome

    return "Não encontrada"


def obter_ip_mascara(interface):
    interfaces = psutil.net_if_addrs()

    if interface not in interfaces:
        return "Não disponível", "Não disponível"

    for endereco in interfaces[interface]:

        if endereco.family == socket.AF_INET:
            return endereco.address, endereco.netmask

    return "Não disponível", "Não disponível"


def obter_estado_conexao(interface):
    estados = psutil.net_if_stats()

    if interface in estados and estados[interface].isup:
        return "Conectado"

    return "Desconectado"


def obter_gateway():
    try:

        resultado = subprocess.run(
            ["ip", "route"],
            capture_output=True,
            text=True,
            timeout=3
        )

        for linha in resultado.stdout.splitlines():

            if linha.startswith("default"):

                partes = linha.split()

                if "via" in partes:

                    indice = partes.index("via")

                    return partes[indice + 1]

    except Exception:
        pass

    return "Não disponível"


def obter_dns():
    servidores = []

    try:

        with open("/etc/resolv.conf", "r") as arquivo:

            for linha in arquivo:

                linha = linha.strip()

                if linha.startswith("nameserver"):

                    partes = linha.split()

                    if len(partes) >= 2:
                        servidores.append(partes[1])

    except Exception:
        pass

    if not servidores:
        servidores.append("Não disponível")

    return servidores


def testar_conectividade(destino):

    momento = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    inicio = time.perf_counter()

    try:

        resultado = subprocess.run(
            ["ping", "-c", "1", "-W", "2", destino],
            capture_output=True,
            text=True,
            timeout=4
        )

        fim = time.perf_counter()

        tempo = (fim - inicio) * 1000

        if resultado.returncode == 0:

            return TesteConectividade(
                destino=destino,
                estado="OK",
                tempo_resposta=f"{tempo:.1f} ms",
                momento=momento
            )

        return TesteConectividade(
            destino=destino,
            estado="Falha",
            tempo_resposta="Sem resposta",
            momento=momento
        )

    except Exception:

        return TesteConectividade(
            destino=destino,
            estado="Falha",
            tempo_resposta="Sem resposta",
            momento=momento
        )


def obter_info_rede():

    nome_equipamento = obter_nome_equipamento()

    interface = obter_interface_rede()

    estado_conexao = obter_estado_conexao(interface)

    ip, mascara = obter_ip_mascara(interface)

    gateway = obter_gateway()

    dns = obter_dns()

    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    testes = []

    # -------------------------------------------------
    # TESTE 1 - GATEWAY DA REDE LOCAL
    # -------------------------------------------------

    if gateway != "Não disponível":

        testes.append(
            testar_conectividade(gateway)
        )

    else:

        testes.append(
            TesteConectividade(
                destino="Gateway",
                estado="Falha",
                tempo_resposta="Indisponível",
                momento=data_hora
            )
        )

    # -------------------------------------------------
    # TESTE 2 - SERVIÇO LOCAL / DNS
    # -------------------------------------------------

    destino_local = None

    for servidor in dns:

        if servidor != "Não disponível":
            destino_local = servidor
            break

    if destino_local is not None:

        testes.append(
            testar_conectividade(destino_local)
        )

    else:

        testes.append(
            TesteConectividade(
                destino="Serviço local",
                estado="Atenção",
                tempo_resposta="Indisponível",
                momento=data_hora
            )
        )

    # -------------------------------------------------
    # TESTE 3 - SERVIÇO EXTERNO
    # -------------------------------------------------

    testes.append(
        testar_conectividade("8.8.8.8")
    )

    return InfoRede(
        nome_equipamento=nome_equipamento,
        interface=interface,
        estado_conexao=estado_conexao,
        ip=ip,
        mascara=mascara,
        gateway=gateway,
        dns=dns,
        data_hora_verificacao=data_hora,
        testes=testes
    )


@app.get("/infoRede", response_model=InfoRede)
def obter_info_rede_api():

    return obter_info_rede()


@app.get("/status", response_class=HTMLResponse)
def obter_status_rede(request: Request):

    info = obter_info_rede()

    return templates.TemplateResponse(
        request,
        "status.html",
        {"dados": info.model_dump()}
    )