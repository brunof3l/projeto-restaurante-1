import banco

CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS estado_restaurante (
    id      INTEGER PRIMARY KEY,
    versao  INTEGER NOT NULL DEFAULT 1,
    dados   TEXT    NOT NULL
)
"""

_tabela_pronta = False


def _conexao():
    global _tabela_pronta
    conexao = banco.conexao()
    if not _tabela_pronta:
        with banco.conexao() as conn:
            conn.execute(CRIAR_TABELA)
        _tabela_pronta = True
    return conexao


def buscar_estado():
    with _conexao() as conn:
        linha = conn.execute("SELECT versao, dados FROM estado_restaurante WHERE id = 1").fetchone()
    return linha


def criar_estado(dados):
    with _conexao() as conn:
        conn.execute(
            "INSERT INTO estado_restaurante (id, versao, dados) VALUES (1, 1, %s) ON CONFLICT (id) DO NOTHING",
            (dados,),
        )


def salvar_estado(dados, versao):
    with _conexao() as conn:
        linha = conn.execute(
            "UPDATE estado_restaurante SET dados = %s, versao = versao + 1 WHERE id = 1 AND versao = %s RETURNING versao",
            (dados, versao),
        ).fetchone()
    return linha is not None
