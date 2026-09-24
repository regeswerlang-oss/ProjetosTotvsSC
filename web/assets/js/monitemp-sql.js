/* ============================================================================
 *  MONITEMP — gerador dos scripts da aba "Empresas e Compartilhamento"
 *
 *  Fonte UNICA dos dois scripts, nos dois dialetos:
 *    P0  scriptSM0()      - leitura MANUAL da SM0 (SYS_COMPANY): empresas,
 *                           filiais, leiaute, e quais tabelas do escopo existem
 *                           em cada empresa. E o passo que prepara o resto.
 *    P1  scriptEmpresas() - a medicao: empresa x tabela x conteudo do campo
 *                           filial, com o compartilhamento da SX2 ao lado.
 *
 *  Roda no navegador (window.MonitEmp) e no node (module.exports) - o mesmo
 *  codigo gera o modal da aba e os arquivos de _entregas. Duas copias da regra
 *  e como um script passa a dizer uma coisa e o painel outra.
 *
 *  Regras que valem para os dois dialetos:
 *   - Somente SELECT, uma consulta, SEM ';' no fim (TSCMONITREST e console).
 *   - Texto do SQL em ASCII puro (nome de filial com acento vira sem acento).
 *   - Mesmas colunas de saida nas duas versoes: o importador aceita qualquer uma.
 *   - Nome de CTE com prefixo Q_: o release Oracle do cliente recusou com
 *     ORA-32031 ("illegal reference of a query name in WITH clause") o script
 *     cujo CTE se chamava SX2 enquanto a saida tinha a coluna SX2. Prefixo em
 *     TODOS os blocos tira a chance de um nome de bloco esbarrar em nome de
 *     coluna, alias ou literal.
 *   - Oracle: nenhuma tabela e referenciada direto - dono e existencia vem do
 *     ALL_TABLES e a leitura e dinamica (DBMS_XMLGEN). Metadado resolvido num
 *     nivel (META) e SQL montado em outro (SQLS): agregado misturado com
 *     subconsulta escalar na mesma expressao ja derrubou o console TCloud.
 *   - SQL Server nao tem SQL dinamico dentro de um SELECT: o script sai com a
 *     existencia congelada na leitura da SM0 (P0). Tabela criada depois so
 *     entra gerando o script de novo - e o P0 precisa ser refeito.
 * ==========================================================================*/
(function (raiz) {
  'use strict';

  // Escopo RH - carga inicial vinda de sistema legado. TIPO separa o que e
  // cadastro (carregado) do que e movimento/historico (importado do legado).
  const LISTA_RH = [
    { tipo: 'CADASTRO', tab: 'SRA', descr: 'Funcionarios' },
    { tipo: 'CADASTRO', tab: 'SRB', descr: 'Dependentes' },
    { tipo: 'CADASTRO', tab: 'SRJ', descr: 'Funcoes' },
    { tipo: 'CADASTRO', tab: 'SQ3', descr: 'Cargos' },
    { tipo: 'CADASTRO', tab: 'SQB', descr: 'Departamentos' },
    { tipo: 'CADASTRO', tab: 'CTT', descr: 'Centro de Custo' },
    { tipo: 'CADASTRO', tab: 'SR6', descr: 'Turnos de Trabalho' },
    { tipo: 'CADASTRO', tab: 'RCE', descr: 'Sindicatos' },
    { tipo: 'CADASTRO', tab: 'SRV', descr: 'Verbas' },
    { tipo: 'CADASTRO', tab: 'SRY', descr: 'Roteiros de Calculo' },
    { tipo: 'CADASTRO', tab: 'RCJ', descr: 'Processos' },
    { tipo: 'CADASTRO', tab: 'RCH', descr: 'Periodos' },
    { tipo: 'CADASTRO', tab: 'SRQ', descr: 'Beneficiarios (Pensao)' },
    { tipo: 'MOVIMENTO', tab: 'SRD', descr: 'Historico de Movimentos (Acumulados)' },
    { tipo: 'MOVIMENTO', tab: 'SRC', descr: 'Movimento do Periodo' },
    { tipo: 'MOVIMENTO', tab: 'RGB', descr: 'Lancamentos por Periodo' },
    { tipo: 'MOVIMENTO', tab: 'SRK', descr: 'Valores Futuros' },
    { tipo: 'MOVIMENTO', tab: 'SR3', descr: 'Historico de Valores Salariais' },
    { tipo: 'MOVIMENTO', tab: 'SR7', descr: 'Historico de Alteracoes Salariais' },
    { tipo: 'MOVIMENTO', tab: 'SRE', descr: 'Transferencias' },
    { tipo: 'MOVIMENTO', tab: 'SR8', descr: 'Controle de Ausencias' },
    { tipo: 'MOVIMENTO', tab: 'SRF', descr: 'Controle de Dias de Direito (Ferias)' },
    { tipo: 'MOVIMENTO', tab: 'SRH', descr: 'Cabecalho de Ferias' },
    { tipo: 'MOVIMENTO', tab: 'SRG', descr: 'Cabecalho de Rescisoes' },
    { tipo: 'MOVIMENTO', tab: 'SRR', descr: 'Itens de Ferias e Rescisoes' },
  ];

  // Colunas de saida - identicas nos dois dialetos, na mesma ordem.
  const COLS_SM0 = ['EMPRESA', 'FILIAL', 'NOME_EMPRESA', 'NOME_FILIAL', 'CNPJ', 'LEIAUTE',
    'SIZEFIL', 'SX2', 'QTD_TABELAS', 'TABELAS_EXISTENTES', 'DT_LEITURA', 'SEMANA'];
  const COLS_EMP = ['EMPRESA', 'NOME_EMPRESA', 'LEIAUTE', 'TIPO', 'TABELA', 'DESCRICAO',
    'TABELA_FISICA', 'SITUACAO', 'SX2', 'FILIAL', 'FILIAL_TIPO', 'NOME_FILIAL', 'QTDE',
    'DT_LEITURA', 'SEMANA'];

  const ascii = (s) => String(s == null ? '' : s).normalize('NFD')
    .replace(/[̀-ͯ]/g, '').replace(/[^\x20-\x7e]/g, ' ');
  const lit = (s) => "'" + ascii(s).replace(/'/g, "''").trim() + "'";
  const cod = (s) => ascii(s).replace(/[^0-9A-Za-z]/g, '').toUpperCase();
  const campoFilial = (tab) => (tab[0] === 'S' ? tab.slice(1, 3) : tab) + '_FILIAL';

  const DT = {
    oracle: "TO_CHAR(SYSDATE, 'DD/MM/YYYY HH24:MI')",
    mssql: 'CONVERT(varchar(16), GETDATE(), 120)',
  };
  const SEMANA = {
    oracle: "TO_CHAR(SYSDATE, 'IYYY') || '-W' || TO_CHAR(SYSDATE, 'IW')",
    mssql: "CONCAT(DATEPART(year, GETDATE()), '-W', FORMAT(DATEPART(ISO_WEEK, GETDATE()), '00'))",
  };
  const NOME_BANCO = { oracle: 'ORACLE', mssql: 'SQL SERVER' };

  function cabecalho(o) {
    const d = o.dialeto === 'oracle' ? 'oracle' : 'mssql';
    return [
      '-- ===========================================================================',
      '-- ' + ascii(o.titulo),
      '-- Cliente: ' + ascii(o.cliente || '-') + '   Base: ' + ascii(o.base || '-'),
      '-- Banco: ' + NOME_BANCO[d] + '   Gerado pela Gestao de Projetos TOTVS SC em ' + ascii(o.quando || ''),
      '--',
      ...o.linhas.map(l => '-- ' + ascii(l)),
      '--',
      '-- Regras: somente SELECT, uma consulta, sem ponto e virgula no fim.',
      '-- ===========================================================================',
    ].join('\n');
  }

  function listaDual(lista, d) {
    const du = d === 'oracle' ? ' FROM DUAL' : '';
    return lista.map((l, i) => i === 0
      ? `    SELECT ${lit(l.tipo)} AS TIPO, ${lit(l.tab)} AS TAB, ${lit(l.descr)} AS DESCR${du}`
      : `    SELECT ${lit(l.tipo)}, ${lit(l.tab)}, ${lit(l.descr)}${du}`).join('\n    UNION ALL\n');
  }

  // ------------------------------------------------------------------------
  //  P0 - leitura da SM0 (SYS_COMPANY). Uma linha por empresa/filial.
  // ------------------------------------------------------------------------
  function scriptSM0(o = {}) {
    const d = o.dialeto === 'oracle' ? 'oracle' : 'mssql';
    const lista = o.lista || LISTA_RH;
    const cab = cabecalho({ ...o, dialeto: d,
      titulo: 'MONITEMP P0 - Leitura da SM0 (empresas, filiais, leiaute e tabelas existentes)',
      linhas: [
        'PASSO MANUAL: rode, confira o resultado com o cliente (quais empresas',
        'e filiais estao ativas, qual o leiaute) e suba o CSV em "Subir SM0".',
        'E a partir desta leitura que o painel monta o script de Empresas.',
        'Le a SYS_COMPANY (a SM0 no banco) e procura, para cada empresa, as',
        lista.length + ' tabelas do escopo (<TAB><EMPRESA>0, ex.: SRA030) e a SX2<EMPRESA>0.',
      ] });

    if (d === 'oracle') {
      return `${cab}
WITH Q_LISTA AS (
${listaDual(lista, d)}
), Q_DONO AS (
    SELECT MIN(OWNER) AS OWNER FROM ALL_TABLES WHERE TABLE_NAME = 'SYS_COMPANY'
), Q_COLS AS (
    SELECT MAX(CASE WHEN C.COLUMN_NAME = 'M0_CGC'     THEN 'S' ELSE 'N' END) AS TEM_CGC,
           MAX(CASE WHEN C.COLUMN_NAME = 'M0_LEIAUTE' THEN 'S' ELSE 'N' END) AS TEM_LEIAUTE,
           MAX(CASE WHEN C.COLUMN_NAME = 'M0_SIZEFIL' THEN 'S' ELSE 'N' END) AS TEM_SIZEFIL,
           MAX(CASE WHEN C.COLUMN_NAME = 'D_E_L_E_T_' THEN 'S' ELSE 'N' END) AS TEM_DEL
      FROM Q_DONO D
      JOIN ALL_TAB_COLUMNS C ON C.OWNER = D.OWNER AND C.TABLE_NAME = 'SYS_COMPANY'
), Q_META AS (
    SELECT D.OWNER,
           CASE WHEN C.TEM_CGC     = 'S' THEN 'TRIM(M0_CGC)'           ELSE 'NULL' END AS X_CGC,
           CASE WHEN C.TEM_LEIAUTE = 'S' THEN 'TRIM(M0_LEIAUTE)'       ELSE 'NULL' END AS X_LEIAUTE,
           CASE WHEN C.TEM_SIZEFIL = 'S' THEN 'M0_SIZEFIL'             ELSE 'NULL' END AS X_SIZEFIL,
           CASE WHEN C.TEM_DEL     = 'S' THEN ' WHERE D_E_L_E_T_ = '' ''' ELSE ' ' END AS X_WHERE
      FROM Q_DONO D CROSS JOIN Q_COLS C
     WHERE D.OWNER IS NOT NULL
), Q_SQLS AS (
    SELECT 'SELECT TRIM(M0_CODIGO) E, TRIM(M0_CODFIL) F, TRIM(M0_NOME) NE, TRIM(M0_FILIAL) NF, ' ||
           M.X_CGC || ' CN, ' || M.X_LEIAUTE || ' LA, ' || M.X_SIZEFIL || ' SZ FROM "' ||
           M.OWNER || '"."SYS_COMPANY"' || M.X_WHERE AS SQL_SM0
      FROM Q_META M
), Q_SM0 AS (
    SELECT X.EMPRESA, X.FILIAL, X.NOME_EMPRESA, X.NOME_FILIAL, X.CNPJ, X.LEIAUTE, X.SIZEFIL
      FROM Q_SQLS S,
           XMLTABLE('/ROWSET/ROW' PASSING DBMS_XMLGEN.GETXMLTYPE(S.SQL_SM0)
                    COLUMNS EMPRESA      VARCHAR2(12)  PATH 'E',
                            FILIAL       VARCHAR2(12)  PATH 'F',
                            NOME_EMPRESA VARCHAR2(100) PATH 'NE',
                            NOME_FILIAL  VARCHAR2(100) PATH 'NF',
                            CNPJ         VARCHAR2(20)  PATH 'CN',
                            LEIAUTE      VARCHAR2(20)  PATH 'LA',
                            SIZEFIL      NUMBER        PATH 'SZ') X
), Q_EMP AS (
    SELECT DISTINCT EMPRESA FROM Q_SM0
), Q_TABS AS (
    SELECT DISTINCT TABLE_NAME FROM ALL_TABLES
), Q_EXISTE AS (
    SELECT E.EMPRESA, COUNT(*) AS QTD,
           LISTAGG(L.TAB, ' ') WITHIN GROUP (ORDER BY L.TAB) AS TABELAS
      FROM Q_EMP E
      JOIN Q_LISTA L ON 1 = 1
      JOIN Q_TABS T ON T.TABLE_NAME = L.TAB || E.EMPRESA || '0'
     GROUP BY E.EMPRESA
), Q_SX2 AS (
    SELECT E.EMPRESA
      FROM Q_EMP E
      JOIN Q_TABS T ON T.TABLE_NAME = 'SX2' || E.EMPRESA || '0'
)
SELECT S.EMPRESA                                      AS EMPRESA,
       S.FILIAL                                       AS FILIAL,
       S.NOME_EMPRESA                                 AS NOME_EMPRESA,
       S.NOME_FILIAL                                  AS NOME_FILIAL,
       S.CNPJ                                         AS CNPJ,
       S.LEIAUTE                                      AS LEIAUTE,
       S.SIZEFIL                                      AS SIZEFIL,
       CASE WHEN X.EMPRESA IS NULL THEN 'N' ELSE 'S' END AS SX2,
       NVL(T.QTD, 0)                                  AS QTD_TABELAS,
       T.TABELAS                                      AS TABELAS_EXISTENTES,
       ${DT.oracle} AS DT_LEITURA,
       ${SEMANA.oracle} AS SEMANA
  FROM Q_SM0 S
  LEFT JOIN Q_EXISTE T ON T.EMPRESA = S.EMPRESA
  LEFT JOIN Q_SX2 X    ON X.EMPRESA = S.EMPRESA
 ORDER BY 1, 2`;
    }

    return `${cab}
-- SQL Server: SYS_COMPANY referenciada direto. Se M0_LEIAUTE ou M0_SIZEFIL nao
-- existirem na release, troque a coluna por NULL nesta consulta.
WITH Q_LISTA AS (
${listaDual(lista, d)}
), Q_SM0 AS (
    SELECT RTRIM(M0_CODIGO)  AS EMPRESA,
           RTRIM(M0_CODFIL)  AS FILIAL,
           RTRIM(M0_NOME)    AS NOME_EMPRESA,
           RTRIM(M0_FILIAL)  AS NOME_FILIAL,
           RTRIM(M0_CGC)     AS CNPJ,
           RTRIM(M0_LEIAUTE) AS LEIAUTE,
           M0_SIZEFIL        AS SIZEFIL
      FROM SYS_COMPANY
     WHERE D_E_L_E_T_ = ' '
)
SELECT S.EMPRESA, S.FILIAL, S.NOME_EMPRESA, S.NOME_FILIAL, S.CNPJ, S.LEIAUTE, S.SIZEFIL,
       CASE WHEN EXISTS (SELECT 1 FROM sys.tables T WHERE T.name = 'SX2' + S.EMPRESA + '0')
            THEN 'S' ELSE 'N' END AS SX2,
       (SELECT COUNT(*) FROM Q_LISTA L JOIN sys.tables T ON T.name = L.TAB + S.EMPRESA + '0') AS QTD_TABELAS,
       STUFF((SELECT ' ' + L.TAB
                FROM Q_LISTA L JOIN sys.tables T ON T.name = L.TAB + S.EMPRESA + '0'
               ORDER BY L.TAB
                 FOR XML PATH('')), 1, 1, '') AS TABELAS_EXISTENTES,
       ${DT.mssql} AS DT_LEITURA,
       ${SEMANA.mssql} AS SEMANA
  FROM Q_SM0 S
 ORDER BY 1, 2`;
  }

  // ------------------------------------------------------------------------
  //  Normaliza as linhas da SM0 (vindas do CSV do P0 ou do banco do painel)
  //  em { empresas: [{empresa, nome, leiaute, sizefil, sx2, tabelas:Set, filiais:[...]}] }
  // ------------------------------------------------------------------------
  function estruturaSM0(linhas, soEmpresas) {
    const mapa = new Map();
    (linhas || []).forEach(r => {
      const e = cod(r.empresa);
      if (!e) return;
      if (soEmpresas && soEmpresas.length && !soEmpresas.includes(e)) return;
      if (!mapa.has(e)) {
        mapa.set(e, { empresa: e, nome: r.nome_empresa || '', leiaute: cod(r.leiaute || ''),
          sizefil: Number(r.sizefil) || null,
          // 'N' no CSV do P0, false no JSON do painel: os dois dizem "sem SX2".
          // Tratar so o 'N' fazia o SQL Server ler SX2020 inexistente (pego no lab).
          sx2: !(r.sx2 === false || ['N', 'FALSE', '0'].includes(String(r.sx2 ?? '').trim().toUpperCase())),
          tabelas: new Set(String(r.tabelas_existentes || r.tabelas || '').toUpperCase()
            .split(/[\s,;]+/).filter(Boolean)), filiais: [] });
      }
      const f = cod(r.filial);
      if (f) mapa.get(e).filiais.push({ filial: f, nome: r.nome_filial || '' });
    });
    return [...mapa.values()].sort((a, b) => a.empresa.localeCompare(b.empresa));
  }

  function literaisEmpFil(emps, d) {
    const du = d === 'oracle' ? ' FROM DUAL' : '';
    const e = emps.map((x, i) => i === 0
      ? `    SELECT ${lit(x.empresa)} AS EMPRESA, ${lit(x.nome)} AS NOME_EMPRESA, ${lit(x.leiaute)} AS LEIAUTE${du}`
      : `    SELECT ${lit(x.empresa)}, ${lit(x.nome)}, ${lit(x.leiaute)}${du}`).join('\n    UNION ALL\n');
    const fl = [];
    emps.forEach(x => x.filiais.forEach(f => fl.push([x.empresa, f.filial, f.nome])));
    if (!fl.length) fl.push(['--', '--', 'sem filial na SM0']);
    const f = fl.map((v, i) => i === 0
      ? `    SELECT ${lit(v[0])} AS EMPRESA, ${lit(v[1])} AS FILIAL, ${lit(v[2])} AS NOME_FILIAL${du}`
      : `    SELECT ${lit(v[0])}, ${lit(v[1])}, ${lit(v[2])}${du}`).join('\n    UNION ALL\n');
    return { e, f };
  }

  // Classificacao do conteudo do campo filial - igual nos dois dialetos.
  // '#' e o marcador de campo em branco (a leitura troca branco por '#').
  function classifica(d, alias) {
    const cc = d === 'oracle' ? ' || ' : ' + ';
    return `       CASE WHEN ${alias}.FILIAL_BRUTA IS NULL THEN NULL
            WHEN ${alias}.FILIAL_BRUTA = '#' THEN 'BRANCO'
            WHEN ${alias}.FILIAL_BRUTA = '*' THEN 'SEM CAMPO FILIAL'
            WHEN EXISTS (SELECT 1 FROM Q_FIL F WHERE F.EMPRESA = ${alias}.EMPRESA AND F.FILIAL = ${alias}.FILIAL_BRUTA)
                 THEN 'FILIAL'
            WHEN EXISTS (SELECT 1 FROM Q_FIL F WHERE F.EMPRESA = ${alias}.EMPRESA AND F.FILIAL LIKE ${alias}.FILIAL_BRUTA${cc}'%')
                 THEN 'PARCIAL'
            WHEN EXISTS (SELECT 1 FROM Q_FIL F WHERE F.FILIAL = ${alias}.FILIAL_BRUTA)
                 THEN 'FILIAL DE OUTRA EMPRESA'
            ELSE 'NAO CADASTRADA NA SM0' END AS FILIAL_TIPO,
       (SELECT MIN(F.NOME_FILIAL) FROM Q_FIL F
         WHERE F.EMPRESA = ${alias}.EMPRESA AND F.FILIAL = ${alias}.FILIAL_BRUTA) AS NOME_FILIAL`;
  }

  // ------------------------------------------------------------------------
  //  P1 - Empresas x tabelas x filial + SX2
  // ------------------------------------------------------------------------
  function scriptEmpresas(o = {}) {
    const d = o.dialeto === 'oracle' ? 'oracle' : 'mssql';
    const lista = o.lista || LISTA_RH;
    const emps = estruturaSM0(o.sm0, o.empresas);
    if (!emps.length) throw new Error('Sem empresas da SM0: rode e suba o P0 (Script SM0) antes de gerar este script.');
    const { e: litE, f: litF } = literaisEmpFil(emps, d);
    const cab = cabecalho({ ...o, dialeto: d,
      titulo: 'MONITEMP - Empresas x Cadastros x Compartilhamento (RH)',
      linhas: [
        'Montado a partir da leitura da SM0 (P0). Empresas: ' + emps.map(x => x.empresa).join(', ') + '.',
        'Uma linha por EMPRESA x TABELA x CONTEUDO DO CAMPO FILIAL, com o',
        'compartilhamento da SX2 da propria empresa ao lado (EMP|UNID|FIL).',
        'SITUACAO: NAO EXISTE (a tabela fisica nao existe) | VAZIA (existe, sem',
        'registro ativo) | COM DADOS | SEM CAMPO FILIAL.',
        'FILIAL_TIPO: BRANCO | FILIAL (codigo da SM0) | PARCIAL (nivel empresa/',
        'unidade) | FILIAL DE OUTRA EMPRESA | NAO CADASTRADA NA SM0.',
        'Exporte em CSV e suba em "Subir medicao" da aba Empresas, ou use',
        '"Coletar agora" (mesmo script, pela REST TSCMONITREST).',
      ].concat(d === 'mssql' ? [
        'SQL SERVER: a existencia das tabelas ficou CONGELADA na leitura da SM0',
        '(tabela que nao existia sai como NAO EXISTE sem ser lida). Criou tabela',
        'nova? Refaca o P0 e gere este script de novo.',
      ] : []) });

    if (d === 'oracle') {
      return `${cab}
WITH Q_EMP AS (
${litE}
), Q_FIL AS (
${litF}
), Q_LISTA AS (
${listaDual(lista, d)}
), Q_ALVO AS (
    SELECT E.EMPRESA, E.NOME_EMPRESA, E.LEIAUTE, L.TIPO, L.TAB, L.DESCR,
           L.TAB || E.EMPRESA || '0'   AS FISICA,
           'SX2' || E.EMPRESA || '0'   AS FISICA_SX2,
           CASE WHEN SUBSTR(L.TAB, 1, 1) = 'S' THEN SUBSTR(L.TAB, 2, 2) ELSE L.TAB END || '_FILIAL' AS CAMPO
      FROM Q_EMP E CROSS JOIN Q_LISTA L
), Q_NOMES AS (
    SELECT FISICA AS NOME FROM Q_ALVO
    UNION
    SELECT FISICA_SX2 FROM Q_ALVO
), Q_TABS AS (
    SELECT T.TABLE_NAME, MIN(T.OWNER) AS OWNER
      FROM ALL_TABLES T
      JOIN Q_NOMES N ON N.NOME = T.TABLE_NAME
     GROUP BY T.TABLE_NAME
), Q_COLS AS (
    SELECT C.OWNER, C.TABLE_NAME, C.COLUMN_NAME
      FROM ALL_TAB_COLUMNS C
      JOIN Q_NOMES N ON N.NOME = C.TABLE_NAME
     WHERE C.COLUMN_NAME LIKE '%FILIAL' OR C.COLUMN_NAME IN ('X2_MODOEMP', 'X2_MODOUN')
), Q_META AS (
    SELECT A.EMPRESA, A.NOME_EMPRESA, A.LEIAUTE, A.TIPO, A.TAB, A.DESCR, A.FISICA,
           A.FISICA_SX2, A.CAMPO, T.OWNER, X.OWNER AS OWNER_SX2,
           CASE WHEN C.COLUMN_NAME  IS NULL THEN 'N' ELSE 'S' END            AS TEM_CAMPO,
           CASE WHEN CE.COLUMN_NAME IS NULL THEN 'NULL' ELSE 'X2_MODOEMP' END AS COL_EMP,
           CASE WHEN CU.COLUMN_NAME IS NULL THEN 'NULL' ELSE 'X2_MODOUN' END  AS COL_UN
      FROM Q_ALVO A
      LEFT JOIN Q_TABS T  ON T.TABLE_NAME = A.FISICA
      LEFT JOIN Q_TABS X  ON X.TABLE_NAME = A.FISICA_SX2
      LEFT JOIN Q_COLS C  ON C.OWNER = T.OWNER  AND C.TABLE_NAME  = A.FISICA     AND C.COLUMN_NAME  = A.CAMPO
      LEFT JOIN Q_COLS CE ON CE.OWNER = X.OWNER AND CE.TABLE_NAME = A.FISICA_SX2 AND CE.COLUMN_NAME = 'X2_MODOEMP'
      LEFT JOIN Q_COLS CU ON CU.OWNER = X.OWNER AND CU.TABLE_NAME = A.FISICA_SX2 AND CU.COLUMN_NAME = 'X2_MODOUN'
), Q_SQLS AS (
    SELECT M.EMPRESA, M.TAB,
           CASE WHEN M.OWNER IS NULL
                THEN 'SELECT ''#'' F, 0 C FROM DUAL WHERE 1 = 0'
                WHEN M.TEM_CAMPO = 'N'
                THEN 'SELECT ''*'' F, COUNT(*) C FROM "' || M.OWNER || '"."' || M.FISICA ||
                     '" WHERE D_E_L_E_T_ = '' '' HAVING COUNT(*) > 0'
                ELSE 'SELECT NVL(TRIM(' || M.CAMPO || '), ''#'') F, COUNT(*) C FROM "' ||
                     M.OWNER || '"."' || M.FISICA || '" WHERE D_E_L_E_T_ = '' '' GROUP BY NVL(TRIM(' ||
                     M.CAMPO || '), ''#'')'
           END AS SQL_DIST,
           CASE WHEN M.OWNER_SX2 IS NULL
                THEN 'SELECT ''x'' M FROM DUAL WHERE 1 = 0'
                ELSE 'SELECT NVL(TRIM(' || M.COL_EMP || '), ''-'') || ''|'' || NVL(TRIM(' ||
                     M.COL_UN || '), ''-'') || ''|'' || NVL(TRIM(X2_MODO), ''-'') M FROM "' ||
                     M.OWNER_SX2 || '"."' || M.FISICA_SX2 || '" WHERE X2_CHAVE = ''' || M.TAB ||
                     ''' AND D_E_L_E_T_ = '' '''
           END AS SQL_SX2
      FROM Q_META M
), Q_MODO AS (
    SELECT S.EMPRESA, S.TAB,
           XMLCAST(XMLQUERY('/ROWSET/ROW[1]/M/text()'
                            PASSING DBMS_XMLGEN.GETXMLTYPE(S.SQL_SX2)
                            RETURNING CONTENT) AS VARCHAR2(20)) AS SX2_MODO
      FROM Q_SQLS S
), Q_DIST AS (
    SELECT S.EMPRESA, S.TAB, X.F AS FILIAL_BRUTA, X.C AS QTDE
      FROM Q_SQLS S,
           XMLTABLE('/ROWSET/ROW' PASSING DBMS_XMLGEN.GETXMLTYPE(S.SQL_DIST)
                    COLUMNS F VARCHAR2(40) PATH 'F',
                            C NUMBER       PATH 'C') X
), Q_BASE AS (
    SELECT M.EMPRESA, M.NOME_EMPRESA, M.LEIAUTE, M.TIPO, M.TAB AS TABELA, M.DESCR AS DESCRICAO,
           M.FISICA AS TABELA_FISICA,
           CASE WHEN M.OWNER IS NULL      THEN 'NAO EXISTE'
                WHEN D.TAB IS NULL        THEN 'VAZIA'
                WHEN M.TEM_CAMPO = 'N'    THEN 'SEM CAMPO FILIAL'
                ELSE 'COM DADOS' END AS SITUACAO,
           CASE WHEN M.OWNER_SX2 IS NULL  THEN 'SEM SX2'
                WHEN O.SX2_MODO IS NULL   THEN 'SEM REGISTRO NA SX2'
                ELSE O.SX2_MODO END AS SX2,
           D.FILIAL_BRUTA, NVL(D.QTDE, 0) AS QTDE
      FROM Q_META M
      LEFT JOIN Q_MODO O ON O.EMPRESA = M.EMPRESA AND O.TAB = M.TAB
      LEFT JOIN Q_DIST D ON D.EMPRESA = M.EMPRESA AND D.TAB = M.TAB
)
SELECT B.EMPRESA, B.NOME_EMPRESA, B.LEIAUTE, B.TIPO, B.TABELA, B.DESCRICAO, B.TABELA_FISICA,
       B.SITUACAO, B.SX2,
       CASE WHEN B.FILIAL_BRUTA = '#' THEN '(branco)'
            WHEN B.FILIAL_BRUTA = '*' THEN '(sem campo)'
            ELSE B.FILIAL_BRUTA END AS FILIAL,
${classifica(d, 'B')},
       B.QTDE,
       ${DT.oracle} AS DT_LEITURA,
       ${SEMANA.oracle} AS SEMANA
  FROM Q_BASE B
 ORDER BY 1, 4, 5, 10`;
    }

    // SQL Server - um bloco por empresa x tabela, com a existencia do P0.
    const blocos = [];
    emps.forEach(x => lista.forEach(l => {
      const fis = l.tab + x.empresa + '0';
      const sx2 = 'SX2' + x.empresa + '0';
      const campo = campoFilial(l.tab);
      const existe = x.tabelas.has(l.tab);
      const modo = x.sx2
        ? `COALESCE((SELECT MAX(ISNULL(NULLIF(RTRIM(X2_MODOEMP), ''), '-') + '|' +
                          ISNULL(NULLIF(RTRIM(X2_MODOUN), ''), '-') + '|' +
                          ISNULL(NULLIF(RTRIM(X2_MODO), ''), '-'))
                   FROM ${sx2} WHERE X2_CHAVE = ${lit(l.tab)} AND D_E_L_E_T_ = ' '), 'SEM REGISTRO NA SX2')`
        : "'SEM SX2'";
      // COALESCE e nao ISNULL: ISNULL herda o tamanho do 1o argumento (5) e
      // cortava 'SEM REGISTRO NA SX2' em 'SEM R' - pego no teste em SQL Server.
      const fixo = `SELECT ${lit(x.empresa)} AS EMPRESA, ${lit(x.nome)} AS NOME_EMPRESA, ${lit(x.leiaute)} AS LEIAUTE,
           ${lit(l.tipo)} AS TIPO, ${lit(l.tab)} AS TABELA, ${lit(l.descr)} AS DESCRICAO, ${lit(fis)} AS TABELA_FISICA,`;
      if (!existe) {
        blocos.push(`    ${fixo}
           'NAO EXISTE' AS SITUACAO,
           ${modo} AS SX2,
           CAST(NULL AS varchar(40)) AS FILIAL_BRUTA, 0 AS QTDE`);
      } else {
        blocos.push(`    ${fixo}
           CASE WHEN G.F IS NULL THEN 'VAZIA' ELSE 'COM DADOS' END AS SITUACAO,
           ${modo} AS SX2,
           G.F AS FILIAL_BRUTA, ISNULL(G.C, 0) AS QTDE
      FROM (SELECT 1 AS UM) U
      LEFT JOIN (SELECT ISNULL(NULLIF(RTRIM(${campo}), ''), '#') AS F, COUNT(*) AS C
                   FROM ${fis} WHERE D_E_L_E_T_ = ' '
                  GROUP BY ISNULL(NULLIF(RTRIM(${campo}), ''), '#')) G ON 1 = 1`);
      }
    }));

    return `${cab}
WITH Q_FIL AS (
${litF}
), Q_BASE AS (
${blocos.join('\n    UNION ALL\n')}
)
SELECT B.EMPRESA, B.NOME_EMPRESA, B.LEIAUTE, B.TIPO, B.TABELA, B.DESCRICAO, B.TABELA_FISICA,
       B.SITUACAO, B.SX2,
       CASE WHEN B.FILIAL_BRUTA = '#' THEN '(branco)' ELSE B.FILIAL_BRUTA END AS FILIAL,
${classifica(d, 'B')},
       B.QTDE,
       ${DT.mssql} AS DT_LEITURA,
       ${SEMANA.mssql} AS SEMANA
  FROM Q_BASE B
 ORDER BY 1, 4, 5, 10`;
  }

  const api = { LISTA_RH, COLS_SM0, COLS_EMP, scriptSM0, scriptEmpresas, estruturaSM0, campoFilial };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else raiz.MonitEmp = api;
})(typeof window !== 'undefined' ? window : globalThis);
