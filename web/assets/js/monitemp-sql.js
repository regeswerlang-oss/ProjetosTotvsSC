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
 *   - Sem SQL dinamico em nenhum dos dois dialetos: o release Oracle do cliente
 *     recusou DBMS_XMLGEN/XMLTABLE (ORA-32031 e, na tentativa seguinte,
 *     ORA-00923). O P0 le a SYS_COMPANY direto e o P1 sai com a existencia
 *     congelada pelo P0 - tabela criada depois so entra gerando o script de
 *     novo, o que exige refazer o P0.
 *   - Tabela que existe sem o campo de filial vem marcada com '*' no P0: citar
 *     coluna inexistente derruba a consulta inteira (ORA-00904), nao so o bloco.
 * ==========================================================================*/
(function (raiz) {
  'use strict';

  // Escopo medido pela aba. GRUPO e o modulo de onde a tabela veio: e rotulo de
  // apresentacao - o painel agrupa a matriz por ele - e NAO entra no layout do
  // CSV nem no banco, para nao invalidar medicao ja gravada. TIPO separa o que e
  // cadastro do que e movimento/historico: na carga do legado os dois vem por
  // caminhos diferentes. A CTT fica em RH porque entrou pelo escopo do RH
  // (centro de custo do funcionario), ainda que a tabela seja da Contabilidade.
  const GRUPOS = ['RH', 'Cadastros Gerais', 'Financeiro', 'Contabilidade'];
  const LISTA_ESCOPO = [
    // --- RH: cadastros ---
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SRA', descr: 'Funcionarios' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SRB', descr: 'Dependentes' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SRJ', descr: 'Funcoes' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SQ3', descr: 'Cargos' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SQB', descr: 'Departamentos' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'CTT', descr: 'Centro de Custo' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SR6', descr: 'Turnos de Trabalho' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'RCE', descr: 'Sindicatos' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SRV', descr: 'Verbas' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SRY', descr: 'Roteiros de Calculo' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'RCJ', descr: 'Processos' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'RCH', descr: 'Periodos' },
    { grupo: 'RH', tipo: 'CADASTRO', tab: 'SRQ', descr: 'Beneficiarios (Pensao)' },
    // --- RH: movimentos e historicos ---
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRD', descr: 'Historico de Movimentos (Acumulados)' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRC', descr: 'Movimento do Periodo' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'RGB', descr: 'Lancamentos por Periodo' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRK', descr: 'Valores Futuros' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SR3', descr: 'Historico de Valores Salariais' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SR7', descr: 'Historico de Alteracoes Salariais' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRE', descr: 'Transferencias' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SR8', descr: 'Controle de Ausencias' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRF', descr: 'Controle de Dias de Direito (Ferias)' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRH', descr: 'Cabecalho de Ferias' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRG', descr: 'Cabecalho de Rescisoes' },
    { grupo: 'RH', tipo: 'MOVIMENTO', tab: 'SRR', descr: 'Itens de Ferias e Rescisoes' },
    // --- Cadastros Gerais: as tres bases que quase toda implantacao carrega ---
    { grupo: 'Cadastros Gerais', tipo: 'CADASTRO', tab: 'SA1', descr: 'Clientes' },
    { grupo: 'Cadastros Gerais', tipo: 'CADASTRO', tab: 'SA2', descr: 'Fornecedores' },
    { grupo: 'Cadastros Gerais', tipo: 'CADASTRO', tab: 'SB1', descr: 'Produtos' },
    // --- Financeiro: parametrizacao do CNAB (TDN FIN0037) ---
    { grupo: 'Financeiro', tipo: 'CADASTRO', tab: 'SEB', descr: 'Ocorrencias CNAB' },
    { grupo: 'Financeiro', tipo: 'CADASTRO', tab: 'SEJ', descr: 'Ocorrencias de Extrato' },
    // --- Contabilidade: as quatro entidades do plano ---
    { grupo: 'Contabilidade', tipo: 'CADASTRO', tab: 'CT1', descr: 'Plano de Contas' },
    { grupo: 'Contabilidade', tipo: 'CADASTRO', tab: 'CTD', descr: 'Itens Contabeis' },
    { grupo: 'Contabilidade', tipo: 'CADASTRO', tab: 'CTH', descr: 'Classes de Valor' },
    { grupo: 'Contabilidade', tipo: 'CADASTRO', tab: 'CT5', descr: 'Lancamentos Padrao' },
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
    const lista = o.lista || LISTA_ESCOPO;
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
      // LEITURA DIRETA da SYS_COMPANY. A versao anterior montava a consulta em
      // tempo de execucao (DBMS_XMLGEN + XMLTABLE) para nao depender de owner
      // nem de coluna opcional. A base da Acosul recusou as duas formas dessa
      // tecnica: ORA-32031 quando o PASSING recebia coluna de CTE e ORA-00923
      // quando recebia subconsulta escalar. Em vez de insistir, referencia
      // direta: se o owner nao for o do usuario conectado o erro e ORA-00942 e
      // basta qualificar; se faltar M0_LEIAUTE ou M0_SIZEFIL e ORA-00904 e
      // basta trocar por NULL. Erros claros, correcao de uma linha.
      return `${cab}
-- Se der ORA-00942 (tabela nao existe), qualifique: "OWNER"."SYS_COMPANY".
-- Se der ORA-00904 em M0_LEIAUTE ou M0_SIZEFIL, troque a coluna por NULL.
WITH Q_LISTA AS (
${listaDual(lista, d)}
), Q_SM0 AS (
    SELECT TRIM(M0_CODIGO)  AS EMPRESA,
           TRIM(M0_CODFIL)  AS FILIAL,
           TRIM(M0_NOME)    AS NOME_EMPRESA,
           TRIM(M0_FILIAL)  AS NOME_FILIAL,
           TRIM(M0_CGC)     AS CNPJ,
           TRIM(M0_LEIAUTE) AS LEIAUTE,
           M0_SIZEFIL       AS SIZEFIL
      FROM SYS_COMPANY
     WHERE D_E_L_E_T_ = ' '
), Q_EMP AS (
    SELECT DISTINCT EMPRESA FROM Q_SM0
), Q_TABS AS (
    SELECT DISTINCT TABLE_NAME FROM ALL_TABLES
), Q_COLS AS (
    SELECT DISTINCT TABLE_NAME, COLUMN_NAME FROM ALL_TAB_COLUMNS
     WHERE COLUMN_NAME LIKE '%FILIAL'
), Q_EXISTE AS (
    -- O '*' depois do nome marca: a tabela existe mas NAO tem o campo filial.
    -- O script de Empresas le essa marca e conta so o total naquela tabela -
    -- referenciar um campo que nao existe derruba a consulta inteira
    -- (ORA-00904 / Invalid column name), e uma tabela boba levaria as 25 junto.
    SELECT E.EMPRESA, COUNT(*) AS QTD,
           LISTAGG(L.TAB || CASE WHEN C.COLUMN_NAME IS NULL THEN '*' ELSE '' END, ' ')
             WITHIN GROUP (ORDER BY L.TAB) AS TABELAS
      FROM Q_EMP E
      JOIN Q_LISTA L ON 1 = 1
      JOIN Q_TABS T ON T.TABLE_NAME = L.TAB || E.EMPRESA || '0'
      LEFT JOIN Q_COLS C ON C.TABLE_NAME = L.TAB || E.EMPRESA || '0'
                        AND C.COLUMN_NAME = CASE WHEN SUBSTR(L.TAB, 1, 1) = 'S'
                                                 THEN SUBSTR(L.TAB, 2, 2) ELSE L.TAB END || '_FILIAL'
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
       -- O '*' depois do nome marca: existe, mas sem o campo filial (ver Oracle).
       STUFF((SELECT ' ' + L.TAB + CASE WHEN CL.name IS NULL THEN '*' ELSE '' END
                FROM Q_LISTA L
                JOIN sys.tables T ON T.name = L.TAB + S.EMPRESA + '0'
                LEFT JOIN sys.columns CL ON CL.object_id = T.object_id
                     AND CL.name = CASE WHEN LEFT(L.TAB, 1) = 'S'
                                        THEN SUBSTRING(L.TAB, 2, 2) ELSE L.TAB END + '_FILIAL'
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
          tabelas: new Set(), semFilial: new Set(), filiais: [] });
        String(r.tabelas_existentes || r.tabelas || '').toUpperCase()
          .split(/[\s,;]+/).filter(Boolean).forEach(t => {
            const nome = t.replace('*', '');
            mapa.get(e).tabelas.add(nome);
            if (t.includes('*')) mapa.get(e).semFilial.add(nome);   // existe, sem campo filial
          });
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
    const lista = o.lista || LISTA_ESCOPO;
    const emps = estruturaSM0(o.sm0, o.empresas);
    if (!emps.length) throw new Error('Sem empresas da SM0: rode e suba o P0 (Script SM0) antes de gerar este script.');
    const { e: litE, f: litF } = literaisEmpFil(emps, d);
    const cab = cabecalho({ ...o, dialeto: d,
      titulo: 'MONITEMP - Empresas x Cadastros x Compartilhamento (RH)',
      linhas: [
        'Montado a partir da leitura da SM0 (P0). Empresas: ' + emps.map(x => x.empresa).join(', ') + '.',
        'Uma linha por EMPRESA x TABELA x CONTEUDO DO CAMPO FILIAL, com o',
        'compartilhamento da SX2 da propria empresa ao lado (EMP|UNID|FIL).',
        'SITUACAO: VAZIA (existe, sem registro ativo) | COM DADOS | SEM CAMPO',
        'FILIAL. Tabela que o P0 nao achou NAO entra aqui: ela nao tem o que',
        'medir e inchava o script (131 tabelas x 3 empresas = 320 KB, que a base',
        'recusa com HTTP 500). O painel recompoe essas linhas como NAO EXISTE',
        'ao gravar, cruzando o escopo com a SM0.',
        'FILIAL_TIPO: BRANCO | FILIAL (codigo da SM0) | PARCIAL (nivel empresa/',
        'unidade) | FILIAL DE OUTRA EMPRESA | NAO CADASTRADA NA SM0.',
        'Exporte em CSV e suba em "Subir medicao" da aba Empresas, ou use',
        '"Coletar agora" (mesmo script, pela REST TSCMONITREST).',
        'A existencia das tabelas fica CONGELADA na leitura da SM0: tabela que',
        'nao existia sai como NAO EXISTE sem ser lida. Criou tabela nova? Refaca',
        'o P0 e gere este script de novo.',
      ] });

    // UM BLOCO POR EMPRESA x TABELA, nos dois dialetos, com a existencia das
    // tabelas congelada na leitura da SM0 (P0).
    //
    // O Oracle tinha uma versao propria, dinamica (ALL_TABLES + DBMS_XMLGEN),
    // que dispensava o P0 para saber o que existe. A base da Acosul recusou
    // essa tecnica em duas formas diferentes (ORA-32031 e ORA-00923), entao os
    // dois bancos passaram a usar o mesmo desenho simples: SQL estatico, tabela
    // referenciada direto, e o que existe vem do P0. Um caminho so para manter.
    const O = d === 'oracle';
    const cc   = O ? ' || ' : ' + ';                       // concatenacao
    const nulo = (x, alt) => O ? `NVL(TRIM(${x}), ${alt})` // vazio vira marcador
                               : `ISNULL(NULLIF(RTRIM(${x}), ''), ${alt})`;
    const zero = (x) => O ? `NVL(${x}, 0)` : `ISNULL(${x}, 0)`;
    const nuloTexto = O ? 'CAST(NULL AS VARCHAR2(40))' : 'CAST(NULL AS varchar(40))';
    const umaLinha  = O ? 'FROM DUAL U' : 'FROM (SELECT 1 AS UM) U';
    const blocos = [];
    emps.forEach(x => lista.forEach(l => {
      const fis = l.tab + x.empresa + '0';
      const sx2 = 'SX2' + x.empresa + '0';
      const campo = campoFilial(l.tab);
      const existe = x.tabelas.has(l.tab);
      const semCampo = x.semFilial.has(l.tab);
      // COALESCE e nao ISNULL no SQL Server: ISNULL herda o tamanho do 1o
      // argumento (5) e cortava 'SEM REGISTRO NA SX2' em 'SEM R'.
      const modo = x.sx2
        ? `COALESCE((SELECT MAX(${nulo('X2_MODOEMP', "'-'")}${cc}'|'${cc}
                          ${nulo('X2_MODOUN', "'-'")}${cc}'|'${cc}
                          ${nulo('X2_MODO', "'-'")})
                   FROM ${sx2} WHERE X2_CHAVE = ${lit(l.tab)} AND D_E_L_E_T_ = ' '), 'SEM REGISTRO NA SX2')`
        : "'SEM SX2'";
      const fixo = `SELECT ${lit(x.empresa)} AS EMPRESA, ${lit(x.nome)} AS NOME_EMPRESA, ${lit(x.leiaute)} AS LEIAUTE,
           ${lit(l.tipo)} AS TIPO, ${lit(l.tab)} AS TABELA, ${lit(l.descr)} AS DESCRICAO, ${lit(fis)} AS TABELA_FISICA,`;
      // Tabela que o P0 nao achou NAO entra no SQL. Ela nao tem nada a medir -
      // o bloco so repetia literais - e era ela que inchava o script: com 131
      // tabelas e 3 empresas sao 393 blocos, ~320 KB numa consulta so, que a
      // base devolve como HTTP 500. O painel recompoe as linhas 'NAO EXISTE'
      // na hora de gravar, cruzando o escopo com a SM0.
      if (!existe) {
        return;
      } else if (semCampo) {
        // Existe, mas sem <PFX>_FILIAL: conta o total e marca com '*', que a
        // classificacao le como SEM CAMPO FILIAL. HAVING sem GROUP BY vale nos
        // dois bancos e faz a tabela vazia devolver nenhuma linha (= VAZIA).
        blocos.push(`    ${fixo}
           CASE WHEN G.F IS NULL THEN 'VAZIA' ELSE 'SEM CAMPO FILIAL' END AS SITUACAO,
           ${modo} AS SX2,
           G.F AS FILIAL_BRUTA, ${zero('G.C')} AS QTDE
      ${umaLinha}
      LEFT JOIN (SELECT '*' AS F, COUNT(*) AS C
                   FROM ${fis} WHERE D_E_L_E_T_ = ' '
                 HAVING COUNT(*) > 0) G ON 1 = 1`);
      } else {
        blocos.push(`    ${fixo}
           CASE WHEN G.F IS NULL THEN 'VAZIA' ELSE 'COM DADOS' END AS SITUACAO,
           ${modo} AS SX2,
           G.F AS FILIAL_BRUTA, ${zero('G.C')} AS QTDE
      ${umaLinha}
      LEFT JOIN (SELECT ${nulo(campo, "'#'")} AS F, COUNT(*) AS C
                   FROM ${fis} WHERE D_E_L_E_T_ = ' '
                  GROUP BY ${nulo(campo, "'#'")}) G ON 1 = 1`);
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
       CASE WHEN B.FILIAL_BRUTA = '#' THEN '(branco)'
            WHEN B.FILIAL_BRUTA = '*' THEN '(sem campo)'
            ELSE B.FILIAL_BRUTA END AS FILIAL,
${classifica(d, 'B')},
       B.QTDE,
       ${DT[d]} AS DT_LEITURA,
       ${SEMANA[d]} AS SEMANA
  FROM Q_BASE B
 ORDER BY 1, 4, 5, 10`;
  }

  // Grupo de uma tabela medida. Medicao antiga (ou tabela tirada do escopo) cai
  // em 'Outros' em vez de desaparecer da tela.
  const grupoDaTabela = (tab) => {
    const achou = LISTA_ESCOPO.find(l => l.tab === cod(tab));
    return achou ? achou.grupo : 'Outros';
  };

  const api = { LISTA_ESCOPO, GRUPOS, grupoDaTabela, COLS_SM0, COLS_EMP,
    scriptSM0, scriptEmpresas, estruturaSM0, campoFilial };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else raiz.MonitEmp = api;
})(typeof window !== 'undefined' ? window : globalThis);
