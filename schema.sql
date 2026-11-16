-- Tabela de funcionários do Restaurante BKV (banco Neon / PostgreSQL).
-- O sistema cria esta tabela sozinho na primeira conexão; este arquivo existe
-- para quem preferir executá-la manualmente no "SQL Editor" do Neon.
--
-- A senha não é guardada aqui. Quem guarda e confere as senhas é o Firebase
-- Authentication; esta tabela só diz quem tem permissão de usar o sistema.

CREATE TABLE IF NOT EXISTS usuarios (
    id                        BIGSERIAL PRIMARY KEY,
    firebase_uid              TEXT        NOT NULL UNIQUE,  -- identificador da conta no Firebase
    nome                      TEXT        NOT NULL,
    email                     TEXT        NOT NULL UNIQUE,  -- sempre em letras minúsculas
    ativo                     BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_login              TIMESTAMPTZ,
    ultimo_envio_recuperacao  TIMESTAMPTZ,
    perfil                    TEXT        NOT NULL DEFAULT 'gerente'  -- gerente, caixa, garcom ou cozinha
);

-- Para bancos criados antes dos perfis (o sistema também faz isso sozinho):
--   ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS perfil TEXT NOT NULL DEFAULT 'gerente';

-- Para mudar o perfil de um funcionário:
--   UPDATE usuarios SET perfil = 'caixa' WHERE email = 'funcionario@exemplo.com';

-- Para bloquear um funcionário sem apagar o histórico:
--   UPDATE usuarios SET ativo = FALSE WHERE email = 'funcionario@exemplo.com';

-- ----------------------------------------------------------------------
-- Recuperação de senha por SMS (colunas acrescentadas à tabela).
-- O sistema também cria estas colunas sozinho; execute à mão só se preferir.
-- ----------------------------------------------------------------------
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS telefone        TEXT,         -- celular, só dígitos, com código do país
    ADD COLUMN IF NOT EXISTS sms_codigo_hash  TEXT,         -- hash do código de 4 números
    ADD COLUMN IF NOT EXISTS sms_validade     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sms_tentativas   INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS sms_ultimo_envio TIMESTAMPTZ;

-- Registrar o celular de um funcionário (ex.: 67 99999-8888):
--   UPDATE usuarios SET telefone = '5567999998888' WHERE email = 'funcionario@exemplo.com';
