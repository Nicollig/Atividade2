from pydantic import BaseModel


class TesteConectividade(BaseModel):
    destino: str
    estado: str
    tempo_resposta: str
    momento: str


class InfoRede(BaseModel):
    nome_equipamento: str
    interface: str
    estado_conexao: str
    ip: str
    mascara: str
    gateway: str
    dns: list[str]
    data_hora_verificacao: str
    testes: list[TesteConectividade]