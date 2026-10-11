# legacy-api-bridge

[![CI](https://github.com/Rafaelcarvalho320/legacy-api-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/Rafaelcarvalho320/legacy-api-bridge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2-092E20)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Uma camada anticorrupção sobre um banco legado: tabelas com nome abreviado,
booleanos em `CHAR(1)`, datas em `VARCHAR(8)` e dinheiro em centavos, expostos
como uma API REST limpa — **sem alterar uma linha do banco**.

> *[English summary below](#english-summary)*

## O problema

Você não pode migrar o banco na terça. O sistema antigo continua rodando, a
folha de pagamento depende dele, e a tabela se chama `TB_CLI` desde 1998.

O que você pode fazer é impedir que o resto do código saiba disso.

Esta é a mesma linha, antes e depois:

```sql
-- TB_CLI, como está no banco
INSERT INTO TB_CLI VALUES
  (1, 'MARIA SILVA', '123.456.789-00', '20200115', 'S', 'N', 'F',
   'maria@exemplo.com', '91999990001', 1);
```

```console
$ curl localhost:8000/api/v1/clients/1/
{
  "code": 1,
  "name": "Maria Silva",
  "legacy_name": "MARIA SILVA",
  "document": "12345678900",
  "document_formatted": "123.456.789-00",
  "document_kind": "cpf",
  "person_type": "individual",
  "email": "maria@exemplo.com",
  "phone": "91999990001",
  "active": true,
  "registered_on": "2020-01-15",
  "city": { "code": 1, "name": "Belem", "state": "PA" }
}
```

Nenhum nome de coluna legada aparece. `'S'` virou `true`, `'20200115'` virou
uma data ISO, o CPF saiu em dígitos e formatado, e o `FL_EXCLUI` sumiu de vista
porque quem está excluído não aparece.

## O banco herdado

O schema em [`legacy/sql/legacy_schema.sql`](legacy/sql/legacy_schema.sql) é
reproduzido fielmente, não limpo. Cada decisão feia ali é uma que aparece de
verdade em sistema dos anos noventa que ainda está no ar:

| No banco | O que significa | Na API |
| --- | --- | --- |
| `TB_CLI`, `NM_CLI`, `CD_PEDIDO` | Nomes abreviados para caber em 8 caracteres | `Client.name`, `Order.code` |
| `FL_ATIVO CHAR(1)` = `'S'`/`'N'` | Booleano. Às vezes `NULL`, às vezes minúsculo | `"active": true` |
| `DT_CADAST VARCHAR(8)` = `'20200115'` | Data. `'00000000'` = não sei | `"registered_on": "2020-01-15"` |
| `VL_TOTAL INTEGER` = `125050` | Centavos, porque float nunca foi confiável | `"total": "1250.50"` |
| `ST_PEDIDO CHAR(1)` = `'F'` | Status, com significado num manual impresso | `"status": "invoiced"` |
| `FL_EXCLUI CHAR(1)` | Soft delete. Nada nunca é apagado | A linha simplesmente não existe |
| Sem nenhuma FK | As relações existem, só não estão escritas | `select_related` funciona |
| PK composta `(CD_PEDIDO, NR_ITEM)` | Sem id surrogate, com buracos na numeração | `items[].number` |

## Onde a tradução mora

Nos **campos**, não nos serializers.

```python
class Client(models.Model):
    name = models.CharField(db_column="NM_CLI", max_length=60)
    registered_on = LegacyDateField(db_column="DT_CADAST")
    active = SimNaoBooleanField(db_column="FL_ATIVO")

    class Meta:
        managed = False
        db_table = "TB_CLI"
```

Traduzir no serializer, ou na view, ou no lugar que precisar do valor é como
uma esquisitice de legado acaba copiada em quarenta arquivos e um deles erra.
No campo, `cliente.active` é `bool` e `cliente.registered_on` é `date` em todo
o código, para sempre.

Cada campo implementa os três ganchos que o Django pede: `from_db_value` (o que
sai da consulta), `to_python` (o que vem de um form ou serializer) e
`get_prep_value` (o que volta pro banco, no formato legado).

`managed = False` em tudo: o Django não criou essas tabelas e nunca deve tentar.
`makemigrations` ignora, e a suíte constrói o schema rodando o mesmo `.sql` que
um DBA reconheceria.

## Cinco bugs que esse tipo de banco produz

Todos apareceram durante o desenvolvimento, nenhum por leitura de código. Cada
um tem teste.

**1. `FL_EXCLUI = 'n'` minúsculo escondeu um cliente vivo.** O manager
comparava com `'N'` exato. Pior: o `get_prep_value` do campo normalizava o
valor da *consulta* também, então filtrar por `['S', 's']` virava `['S', 'S']`
e nenhuma linha minúscula era alcançável. Resolvido com os helpers
`flag_true()` / `flag_false()` e um escape para caractere único.

**2. `NOT IN` contra `NULL` é `NULL`.** Pedir "inativos" com
`~Q(active__in=[...])` perdia exatamente as linhas cujo flag é nulo — que é
como "não" foi registrado por anos. O ramo `isnull` não é zelo, é obrigatório.

**3. Toda data virou `None`.** O campo herdava de `DateField`, e o Django
escolhe os conversores dele pelo tipo interno e os roda **antes** do
`from_db_value`. O backend recebia `'20200115'`, não conseguia ler como ISO e
entregava `None`. Resolvido com `get_internal_type()` devolvendo `"CharField"`.

**4. Centavos convertidos duas vezes.** O filtro `min_total` multiplicava por
100 e o campo multiplicava de novo, então o limiar ficava cem vezes maior e a
consulta não casava com nada, silenciosamente. Quem sabe de centavos é um lugar
só.

**5. O schema funcionava em SQLite e não existia no PostgreSQL.** `CREATE TABLE
TB_CLI` sem aspas faz o Postgres criar uma tabela chamada `tb_cli`, porque ele
rebaixa identificador não citado para minúsculas. O Django emite
`FROM "TB_CLI"`, que é case-sensitive, e os dois nunca se encontram:
`relation "TB_CLI" does not exist`. Todo identificador no DDL passou a ser
citado. Esse é o motivo de a CI rodar a suíte contra PostgreSQL de verdade e não
só contra SQLite — em SQLite o nome de tabela é case-insensitive e o bug é
invisível.

## Rodando

```bash
python -m venv .venv && source .venv/Scripts/activate   # Linux/macOS: .venv/bin/activate
pip install -r requirements-dev.txt

export DJANGO_SECRET_KEY=dev DJANGO_DEBUG=true
python manage.py migrate        # só as tabelas do próprio Django
python manage.py load_legacy    # cria TB_* a partir do SQL e popula
python manage.py runserver
```

```console
$ python manage.py load_legacy
legacy schema created
  clients visible: 7 (of 8 rows in TB_CLI)
  orders visible:  7 (of 8 rows in TB_PED)
  order lines:     8
```

A diferença entre 7 e 8 é o soft delete funcionando. Em `/admin/` você vê as 8,
porque o admin é a ferramenta que você usa justamente quando precisa ver o que
a API esconde.

## A API

| Rota | O quê |
| --- | --- |
| `GET /api/v1/clients/` | Lista. Filtra por `active`, `state`, `city`, `document`, `registered_after` |
| `GET /api/v1/clients/{code}/` | Detalhe |
| `GET /api/v1/orders/` | Lista. Filtra por `status`, `client`, `min_total`, `issued_after` |
| `GET /api/v1/orders/{code}/` | Detalhe, com as linhas do pedido |
| `GET /api/v1/cities/` | Lista |

Filtros falam a linguagem do domínio, nunca a do legado:

```console
$ curl "localhost:8000/api/v1/orders/?status=invoiced"     # não ?ST_PEDIDO=F
$ curl "localhost:8000/api/v1/clients/?active=true"        # acha o 's' minúsculo
$ curl "localhost:8000/api/v1/clients/?document=123.456.789-00"  -> 1 resultado
$ curl "localhost:8000/api/v1/clients/?document=12345678900"     -> 1 resultado
```

Os dois últimos acham a **mesma** linha. A tabela guarda as duas grafias porque
duas telas diferentes escreveram nela, então um `LIKE` no valor cru acharia uma
e perderia a outra. A comparação é feita por dígitos; a correção de verdade
seria uma coluna gerada no banco, e isso precisa de um DBA.

## Somente leitura, de propósito

Não é limitação. A aplicação legada continua rodando e continua escrevendo
nessas tabelas, e ela carrega invariantes que não estão escritas em lugar
nenhum que um segundo escritor pudesse descobrir. Expor leitura primeiro é a
metade útil de um *strangler fig*, e não tem como corromper nada.

Os campos já sabem escrever de volta — `get_prep_value` devolve `'S'`,
`'20240307'` e centavos — então quando houver acordo sobre quem é o dono da
escrita, o caminho existe e está testado.

## O que a API não esconde

Um banco de vinte anos tem contradições, e inventar coerência seria a API
mentindo:

- **Pedido 1001**: `VL_TOTAL` diz `1250.50`, a soma das linhas dá `350.00`. Os
  dois números aparecem, como `total` e `items_total`.
- **Pedido 1007**: `ST_PEDIDO = 'X'`, que não está no manual. Vira
  `"status": "unknown"` com `"status_code": "X"` ao lado, para alguém poder ir
  perguntar o que era.
- **Cliente 8**: aponta para a cidade 999, que não existe. `city` vem `null`
  em vez de estourar.
- **Pedido 1008**: pertence a um cliente soft-deletado. Lista normalmente, com
  `client_name: null` — o `select_related` passa por cima do manager, então o
  vazamento é barrado no serializer. O código continua visível, para a
  referência ficar rastreável.

## Testes

```bash
pytest                  # 108 testes
ruff check . && ruff format --check .
mypy                    # strict, com django-stubs
```

As tabelas legadas são criadas dentro da transação que o pytest-django abre
para cada teste, a partir dos mesmos `.sql` do demo. Uma descrição do schema,
não duas que divergem com o tempo.

Localmente roda em SQLite. A CI roda a suíte inteira contra **PostgreSQL de
verdade** também, porque o schema é portável mas o ponto do projeto é lidar com
um banco real.

```
legacy/
    sql/legacy_schema.sql   o schema herdado, reproduzido fielmente
    sql/legacy_seed.sql     dados de exemplo, com os casos sujos
    fields.py               onde o formato legado para
    translators.py          regras puras: status, documento, texto
    models.py               managed=False sobre as TB_*
    filters.py              filtros em linguagem de domínio
    serializers.py          a forma que o mundo externo vê
    admin.py                telas somente-leitura para investigar
tests/                      108 testes
```

## English summary

An anti-corruption layer over an inherited database: abbreviated table names,
booleans in `CHAR(1)`, dates in `VARCHAR(8)`, money in integer cents and no
foreign keys anywhere — exposed as a clean REST API **without changing a single
column**.

The idea is that the translation lives in **custom model fields**, not in
serializers. Translating at the serializer, or the view, or wherever a value
happens to be needed is how one legacy quirk ends up copy-pasted into forty
places and one of them gets it wrong. In the field, `client.active` is a `bool`
and `client.registered_on` is a `date` everywhere, forever.

Four bugs this kind of database produces, all found by running it and all now
covered by tests:

- A lowercase `'n'` in the soft-delete column hid a live customer, and the
  field's own `get_prep_value` normalised query values too, so filtering on
  both spellings was impossible until an escape hatch was added.
- `NOT IN` against `NULL` is `NULL`, so asking for "inactive" dropped exactly
  the rows whose flag was never set — which is how "no" was recorded for years.
- Every date silently became `None`, because Django picks value converters from
  a field's internal type and runs them *before* `from_db_value`.
- A cents threshold was multiplied by a hundred twice, and the filter quietly
  matched nothing.

Read-only is a decision, not a limitation: the legacy application still owns
these tables. The fields already know how to write back, so the path exists and
is tested for when ownership is agreed.

Code and docstrings are in English; the sections above are in Portuguese.

## Licença

MIT. Veja [LICENSE](LICENSE).
