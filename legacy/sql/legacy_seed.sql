-- Sample data, including the messy cases that make the translation layer
-- necessary rather than decorative.

INSERT INTO "TB_CID" ("CD_CIDADE", "NM_CIDADE", "SG_UF") VALUES
    (1, 'BELEM', 'PA'),
    (2, 'SAO PAULO', 'SP'),
    (3, 'RIO DE JANEIRO', 'RJ');

INSERT INTO "TB_CLI" ("CD_CLI", "NM_CLI", "NR_CPFCNPJ", "DT_CADAST", "FL_ATIVO", "FL_EXCLUI", "TP_PESSOA", "NM_EMAIL", "NR_FONE", "CD_CIDADE") VALUES
    -- A perfectly ordinary row.
    (1, 'MARIA SILVA', '123.456.789-00', '20200115', 'S', 'N', 'F', 'maria@exemplo.com', '91999990001', 1),
    -- Same document, written without punctuation. Two systems, two habits.
    (2, 'JOAO SOUZA', '98765432100', '20210320', 'S', 'N', 'F', 'joao@exemplo.com', '(91) 99999-0002', 1),
    -- NULL flag, which the manual says means "no".
    (3, 'EMPRESA ABC LTDA', '12.345.678/0001-95', '20190710', NULL, 'N', 'J', NULL, NULL, 2),
    -- Lowercase flag. Nothing stopped it.
    (4, 'PEDRO LIMA', '11122233344', '20221101', 's', 'n', 'F', 'pedro@exemplo.com', NULL, 3),
    -- Soft-deleted: still in the table, must never reach the API.
    (5, 'CLIENTE REMOVIDO', '55566677788', '20180101', 'S', 'S', 'F', NULL, NULL, 1),
    -- The sentinel date, meaning "we do not know".
    (6, 'ANA PEREIRA', '99988877766', '00000000', 'S', 'N', 'F', 'ana@exemplo.com', '91988880006', 2),
    -- Inactive but not deleted. A real distinction in the legacy system.
    (7, 'CARLOS ANTIGO', '44455566677', '20170505', 'N', 'N', 'F', NULL, NULL, 3),
    -- Points at a city that does not exist. No constraint ever stopped it.
    (8, 'ORFAO SEM CIDADE', '33344455566', '20230801', 'S', 'N', 'F', NULL, NULL, 999);

INSERT INTO "TB_PED" ("CD_PEDIDO", "CD_CLI", "DT_EMISSAO", "VL_TOTAL", "ST_PEDIDO", "FL_EXCLUI", "OBS_PEDIDO") VALUES
    (1001, 1, '20240110', 125050, 'A', 'N', 'ENTREGAR PELA MANHA'),
    (1002, 1, '20240215', 8990,   'F', 'N', NULL),
    (1003, 2, '20240220', 450000, 'P', 'N', 'AGUARDANDO PAGAMENTO'),
    (1004, 3, '20240301', 230051, 'A', 'N', NULL),
    (1005, 4, '20240315', 7500,   'C', 'N', 'CANCELADO PELO CLIENTE'),
    -- Soft-deleted order.
    (1006, 1, '20240320', 31000,  'A', 'S', NULL),
    -- Unknown status letter: not in the manual, and the API must not crash.
    (1007, 2, '20240401', 12000,  'X', 'N', NULL),
    -- Order whose client was soft-deleted.
    (1008, 5, '20240405', 99900,  'F', 'N', NULL);

INSERT INTO "TB_PEDITE" ("CD_PEDIDO", "NR_ITEM", "DS_PRODUTO", "QT_ITEM", "VL_UNIT") VALUES
    (1001, 1, 'PARAFUSO SEXTAVADO 10MM', 100, 150),
    (1001, 2, 'PORCA 10MM',              100, 100),
    (1001, 3, 'ARRUELA LISA 10MM',       200, 50),
    (1002, 1, 'FITA ISOLANTE',            10, 899),
    (1003, 1, 'CHAPA DE ACO 2MM',          5, 90000),
    -- Line 2 was deleted years ago; the gap is part of the data now.
    (1003, 3, 'ELETRODO 2.5MM',           20, 500),
    (1004, 1, 'TINTA ACRILICA 18L',        1, 230051),
    (1005, 1, 'LIXA 120',                 15, 500);
