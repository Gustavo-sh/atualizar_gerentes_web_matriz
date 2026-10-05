import pyodbc
from telegram_config import notify_telegram

CONNECTION_STRING = "Driver={ODBC Driver 18 for SQL Server};Server=primno4;Database=Robbyson;Trusted_Connection=yes;TrustServerCertificate=yes;"

attributes_hmn = """
set nocount on
select distinct
    matricula,
    atributo,
    gerente,
    matrgerente,
    gerentepleno,
    matrgerentepleno,
    gerentesenior,
    matrgerentesenior
into #base_hmn
from rlt.hmn (nolock) where data = convert(date, getdate()-1)
and situacaohominum in ('ativo')
    and tipohierarquia = 'operação'
    and nivelhierarquico = 'operacional'
    and funcaorm not like 'auxiliar%'
    and funcaorm not like 'analista%'
    and atributo is not null


select distinct
    atributo,
    case when gerentesenior is not null then gerentesenior
         when GERENTEPLENO is not null then GERENTEPLENO
         when gerente is not null then gerente
    else null end as Gerente,
    case when gerentesenior is not null then 1
         when GERENTEPLENO is not null then 2
         when gerente is not null then 3
    else null end as nivel_hierarquico
into #gerentes_por_atributo
from #base_hmn


select
    gerente,
    matrgerente as matricula,
    count(matricula) as hc
into #hc_gerentes
from #base_hmn
group by gerente, matrgerente
union all
select
    gerentepleno,
    matrgerentepleno as matricula,
    count(matricula) as hc
from #base_hmn
group by gerentepleno, matrgerentepleno
union all
select
    gerentesenior,
    matrgerentesenior as matricula,
    count(matricula) as hc
from #base_hmn
group by gerentesenior, matrgerentesenior


select distinct
    gpa.atributo,
    gpa.gerente,
    gpa.nivel_hierarquico,
    hg.hc,
    row_number() over (partition by gpa.atributo order by gpa.nivel_hierarquico, hg.hc asc) as rn
into #final
from #gerentes_por_atributo gpa
left join #hc_gerentes hg
on gpa.gerente = hg.gerente
where gpa.gerente is not null


select DISTINCT
    atributo,
    gerente,
    nivel_hierarquico,
    hc
from #final
where rn = 1
and atributo is not null
and gerente is not null
"""

attributes_sm = """
set nocount on
select distinct
    atributo,
    gerente
from sistema_matriz (nolock)
where periodo = dateadd(d, 1, eomonth(getdate(), 0))
"""

def main():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    try:
        cursor.execute(attributes_hmn)
        ats_hmn = [(r[0], r[1]) for r in cursor.fetchall()]

        cursor.execute(attributes_sm)
        ats_sm = {r[0]: r[1] for r in cursor.fetchall()}

        atualizacoes = []

        for atributo, gerente_hmn in ats_hmn:
            gerente_hmn = (gerente_hmn or "").strip().upper()
            gerente_sm = (ats_sm.get(atributo) or "").strip().upper()

            if gerente_hmn != gerente_sm:
                atualizacoes.append((gerente_hmn, atributo))

        if atualizacoes:
            cursor.executemany("""
                UPDATE sistema_matriz
                SET gerente = ?
                WHERE atributo = ?
                AND periodo = DATEADD(DAY, 1, EOMONTH(GETDATE(), 0))
            """, atualizacoes)

            conn.commit()
    except Exception as e:
        notify_telegram("⚠️ Erro na execução da atualização automática de gerentes da sistema matriz:\n" + str(e))
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__": 
    main()