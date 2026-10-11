-- The legacy schema, as inherited.
--
-- Every ugly decision here is one that really shows up in systems written in
-- the nineties and still running payroll today. It is reproduced faithfully
-- rather than cleaned up, because the whole point of this project is the layer
-- that copes with it: you cannot migrate the database on Tuesday, but you can
-- stop the rest of the codebase from knowing what it looks like.
--
--   * Table and column names are abbreviated, uppercase and Portuguese, often
--     truncated to fit an 8-character limit nobody remembers the reason for.
--   * Booleans are CHAR(1) holding 'S' or 'N'. Sometimes NULL, meaning "no".
--   * Dates are VARCHAR(8) holding YYYYMMDD. '00000000' means "not set".
--   * Money is an integer in cents, because floats were never trusted.
--   * There are no foreign key constraints at all. The relationships exist,
--     they are just not written down anywhere the database can enforce them.
--   * Status is a single letter whose meaning lives in a paper manual.
--   * Soft deletes: rows are never removed, only flagged.

CREATE TABLE TB_CLI (
    CD_CLI      INTEGER      NOT NULL PRIMARY KEY,
    NM_CLI      VARCHAR(60)  NOT NULL,
    NR_CPFCNPJ  VARCHAR(18),
    DT_CADAST   VARCHAR(8),
    FL_ATIVO    CHAR(1),
    FL_EXCLUI   CHAR(1),
    TP_PESSOA   CHAR(1),
    NM_EMAIL    VARCHAR(80),
    NR_FONE     VARCHAR(20),
    CD_CIDADE   INTEGER
);

CREATE TABLE TB_CID (
    CD_CIDADE   INTEGER      NOT NULL PRIMARY KEY,
    NM_CIDADE   VARCHAR(60)  NOT NULL,
    SG_UF       CHAR(2)      NOT NULL
);

CREATE TABLE TB_PED (
    CD_PEDIDO   INTEGER      NOT NULL PRIMARY KEY,
    CD_CLI      INTEGER      NOT NULL,
    DT_EMISSAO  VARCHAR(8),
    VL_TOTAL    INTEGER,
    ST_PEDIDO   CHAR(1),
    FL_EXCLUI   CHAR(1),
    OBS_PEDIDO  VARCHAR(255)
);

-- Composite primary key, no surrogate id, and the line number is part of the
-- identity. Deleting line 2 of a three-line order leaves 1 and 3.
CREATE TABLE TB_PEDITE (
    CD_PEDIDO   INTEGER      NOT NULL,
    NR_ITEM     INTEGER      NOT NULL,
    DS_PRODUTO  VARCHAR(80)  NOT NULL,
    QT_ITEM     INTEGER      NOT NULL,
    VL_UNIT     INTEGER      NOT NULL,
    PRIMARY KEY (CD_PEDIDO, NR_ITEM)
);
