"""Steam Insights | Project B dashboard. Run: streamlit run app.py

Place in proyecto_B/ alongside sql/, scripts/db_conn.py and password.txt.
All filters, joins, aggregation and derived metrics are calculated by PostgreSQL.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
from decimal import Decimal
import html
import plotly.graph_objects as go
import streamlit as st
from psycopg2.extras import RealDictCursor
from scripts.db_conn import get_connection

ROOT = Path(__file__).resolve().parent
SQL_DIR = ROOT / "sql"
SCHEMA = "steam"
BLUE = "#66c0f4"
LIGHT = "#c7d5e0"
GREEN = "#a4d007"
BG = "#0e1722"

st.set_page_config(page_title="Steam Insights | Project B", page_icon="🎮", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"], [data-testid="stApp"] {font-family:'Inter', sans-serif;}
[data-testid="stApp"] {background:linear-gradient(140deg,#0b141e 0%,#152638 46%,#101a26 100%);color:#c7d5e0;}
[data-testid="stSidebar"] {background:linear-gradient(175deg,#162b3a,#101c29);border-right:1px solid #294052;}
[data-testid="stHeader"] {background:transparent;}
.block-container {max-width:1450px;padding-top:1.4rem;padding-bottom:3.5rem;}
h1,h2,h3,h4 {color:#f1f6fc;letter-spacing:-.03em;}
h1 {font-weight:800;}
[data-testid="stMetric"] {background:linear-gradient(145deg,#1c3447,#142434);border:1px solid #31516a;border-radius:10px;padding:16px 18px;box-shadow:0 8px 24px #0002;}
[data-testid="stMetricLabel"] {color:#9eb8cb;}
[data-testid="stMetricValue"] {color:#f3f8fe;font-size:1.7rem;}
.stTabs [data-baseweb="tab-list"] {gap:8px;border-bottom:1px solid #31495b;}
.stTabs [data-baseweb="tab"] {background:#1a2e40;border-radius:8px 8px 0 0;color:#d4e4ee;padding:11px 20px;}
.stTabs [aria-selected="true"] {background:#274761;color:#66c0f4;}
.stButton>button[kind="primary"] {background:linear-gradient(90deg,#287da7,#66c0f4);color:#061523;border:0;font-weight:700;}
.stButton>button {border-radius:6px;}
[data-testid="stDataFrame"] {border:1px solid #294457;border-radius:8px;}
[data-testid="stExpander"] {border:1px solid #304a60;border-radius:8px;background:#142637;}
.stAlert {border-radius:8px;}
.hero {background:radial-gradient(circle at 83% 10%,#235077 0%,transparent 33%),linear-gradient(110deg,#182d3e,#101b28);border:1px solid #34526a;border-radius:12px;padding:26px 30px;margin-bottom:22px;}
.hero .kicker {font-size:11px;color:#8cc8ec;letter-spacing:.16em;font-weight:800;}
.hero h1 {font-size:2.25rem;margin:9px 0 6px;}
.hero p {font-size:14px;color:#b6cada;margin:0;}
.section-title {border-left:3px solid #66c0f4;padding-left:12px;margin:28px 0 15px;color:#ecf5fc;font-size:18px;font-weight:800;}
.small-hint {color:#8faabc;font-size:13px;margin:4px 0 12px;}
.st-key-status {color:#a4d007;}
</style>
""", unsafe_allow_html=True)


# Database calls: every statement uses psycopg2, user input always travels as parameters.
# Do not pass user-controlled SQL identifiers into these functions.
@st.cache_data(ttl=900, show_spinner=False)
def read_sql(query: str, params: tuple = ()) -> list[dict]:
    conn = get_connection(dbname="steam_db")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '90000'")
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.rollback()  # read-only; never leave open transactions
        conn.close()


def run_local_sql(query: str) -> list[dict]:
    """Run a checked-in SQL file, never text supplied by dashboard users."""
    conn = get_connection(dbname="steam_db")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '120000'")
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()] if cur.description else []
    finally:
        conn.rollback()
        conn.close()


def simulate_discount() -> list[dict]:
    # Q10: actual UPDATE inside a transaction. We obtain RETURNING before a guaranteed rollback.
    query = """
        WITH targets AS (
            SELECT app_id, price_final AS previous_price
            FROM steam.games
            WHERE price_final > 0 AND user_reviews IS NOT NULL
            ORDER BY user_reviews DESC, app_id ASC
            LIMIT 10
        )
        UPDATE steam.games AS g
        SET price_final = ROUND(g.price_final * 0.90, 2)
        FROM targets AS t
        WHERE g.app_id = t.app_id
        RETURNING g.app_id, g.title, t.previous_price,
                  g.price_final AS simulated_price, 10 AS campaign_discount_pct
    """
    conn = get_connection(dbname="steam_db")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '20000'")
            cur.execute(query)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.rollback()  # ALWAYS rollback, even if the query or UI fails
        conn.close()


@st.cache_data(ttl=3600, show_spinner=False)
def table_registry() -> list[dict]:
    return read_sql("""
        SELECT c.relname AS table_name,
               GREATEST(c.reltuples, 0)::BIGINT AS estimated_rows,
               (SELECT COUNT(*) FROM information_schema.columns AS co
                WHERE co.table_schema = 'steam' AND co.table_name = c.relname) AS columns_count
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'steam' AND c.relkind IN ('r','p')
        ORDER BY CASE c.relname
          WHEN 'games' THEN 1 WHEN 'users' THEN 2 WHEN 'recommendations' THEN 3
          WHEN 'tags' THEN 4 WHEN 'game_tags' THEN 5 WHEN 'platforms' THEN 6
          WHEN 'game_platforms' THEN 7 ELSE 99 END, c.relname
    """)


@st.cache_data(ttl=3600, show_spinner=False)
def column_registry(table: str) -> list[dict]:
    return read_sql("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'steam' AND table_name = %s
        ORDER BY ordinal_position
    """, (table,))


@st.cache_data(ttl=3600, show_spinner=False)
def year_bounds() -> tuple[int, int]:
    rows = read_sql("""
        SELECT EXTRACT(YEAR FROM MIN(date_release))::INTEGER AS min_year,
               EXTRACT(YEAR FROM MAX(date_release))::INTEGER AS max_year
        FROM steam.games WHERE date_release IS NOT NULL
    """)
    low, high = rows[0]["min_year"], rows[0]["max_year"]
    return int(low or 2000), int(high or date.today().year)


@st.cache_data(ttl=3600, show_spinner=False)
def filter_options() -> tuple[list[str], list[str]]:
    ratings = read_sql("SELECT DISTINCT rating FROM steam.games WHERE rating IS NOT NULL ORDER BY rating")
    platforms = read_sql("SELECT platform_name FROM steam.platforms ORDER BY platform_name")
    return [r['rating'] for r in ratings], [r['platform_name'] for r in platforms]


def plot_style(fig: go.Figure, height: int = 370, percent: bool = False) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Arial", color=LIGHT, size=12),
        margin=dict(l=10, r=14, t=30, b=10), height=height,
        hoverlabel=dict(bgcolor="#243b4e", font_color="#e8f3ff"),
        xaxis=dict(gridcolor="#314253", zeroline=False),
        yaxis=dict(gridcolor="#314253", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
    )
    if percent:
        fig.update_yaxes(ticksuffix="%", range=[0, 100])
    return fig


def num(val, digits=0) -> str:
    if val is None:
        return "—"
    return f"{float(val):,.{digits}f}"


def show_table(rows: list[dict], height=390):
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True, height=height)
    else:
        st.info("No results for the selected filters.")


QUERIES = [
    ("q1_top_20_games_rating.sql", "Top 20 highest-rated games", "Standard"),
    ("q2_platforms_compatible_games.sql", "Compatible games by platform", "Standard"),
    ("q3_top15_tags.sql", "Most popular game tags", "Standard"),
    ("q4_rating_cat_avgs.sql", "Average price & reviews by rating", "Standard"),
    ("q5_top10_recommended_games.sql", "Most positively recommended games", "Standard"),
    ("q6_recommendations_avg_playtime.sql", "Average playtime by recommendation", "Standard"),
    ("q7_top3_rated_per_release_year.sql", "Best three games per release year", "Advanced"),
    ("q8_positive_change_monthly.sql", "Monthly recommendation change", "Advanced"),
    ("q9_higher_positive_than_avg_cat.sql", "Games above category average", "Advanced"),
    ("q10_simulating_discounts_top10.sql", "Simulate a discount campaign", "Advanced"),
]

# Optimized, equivalent-in-purpose Q9 to avoid correlated scans on each candidate.
OPTIMIZED_Q9 = """
WITH category_averages AS (
    SELECT rating, AVG(positive_ratio) AS avg_ratio
    FROM steam.games
    WHERE positive_ratio IS NOT NULL AND user_reviews >= 1000
    GROUP BY rating
)
SELECT g.app_id, g.title, g.rating, g.positive_ratio, g.user_reviews,
       ROUND(c.avg_ratio, 2) AS category_avg_ratio
FROM steam.games AS g
JOIN category_averages AS c ON g.rating = c.rating
WHERE g.positive_ratio IS NOT NULL AND g.user_reviews >= 1000
  AND g.positive_ratio > c.avg_ratio
ORDER BY g.positive_ratio DESC, g.user_reviews DESC, g.app_id ASC
LIMIT 30;
"""


def build_game_conditions(years, rating, platform, pricing, min_reviews):
    """Only data values are dynamic, never identifiers or SQL syntax supplied by the user."""
    cond = ["EXTRACT(YEAR FROM g.date_release) BETWEEN %s AND %s", "COALESCE(g.user_reviews,0) >= %s"]
    vals: list = [years[0], years[1], min_reviews]
    if rating != "All ratings":
        cond.append("g.rating = %s")
        vals.append(rating)
    if platform != "All platforms":
        cond.append("EXISTS (SELECT 1 FROM steam.game_platforms AS gp2 JOIN steam.platforms AS p2 ON gp2.platform_id=p2.platform_id WHERE gp2.app_id=g.app_id AND p2.platform_name=%s)")
        vals.append(platform)
    if pricing == "Paid games":
        cond.append("g.price_final > 0")
    elif pricing == "Free games":
        cond.append("g.price_final = 0")
    return " AND ".join(cond), tuple(vals)


def home_overview():
    st.markdown('<div class="section-title">Database inventory</div>', unsafe_allow_html=True)
    st.caption("Seven relational tables. Row counts below are PostgreSQL planner estimates (fast even for very large tables). Run ANALYZE in PostgreSQL to refresh estimates.")
    registry = table_registry()
    if not registry:
        st.error("The steam schema has no tables. Run your data pipeline first.")
        return
    cards = st.columns(4)
    for i, row in enumerate(registry):
        with cards[i % 4]:
            st.metric(row['table_name'].replace('_',' ').title(), num(row['estimated_rows']), help=f"Estimated rows · {row['columns_count']} columns")
    st.divider()
    table_names = [r['table_name'] for r in registry]
    a, b = st.columns([3, 1])
    with a:
        chosen = st.selectbox("Explore a table", table_names, format_func=lambda x: x.replace('_',' ').title())
    with b:
        limit = st.select_slider("Preview rows", options=[5, 10, 20, 50, 100], value=10)

    # chosen is sourced ONLY from pg_catalog and checked against the returned whitelist.
    if chosen not in table_names:
        st.error("Unknown table")
        return
    columns = column_registry(chosen)
    st.markdown('<div class="section-title">Table snapshot</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    cols[0].metric("Columns", len(columns))
    nullable = read_sql("SELECT COUNT(*) AS n FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND is_nullable='YES'", ('steam', chosen))[0]['n']
    cols[1].metric("Nullable columns", num(nullable))
    cols[2].metric("Estimated rows", num(next(x['estimated_rows'] for x in registry if x['table_name']==chosen)))

    # Summary calculations are deliberately performed in SQL and only for the selected table.
    summary_sql = {
        "games": "SELECT COUNT(*) AS total_games, COUNT(*) FILTER (WHERE price_final=0) AS free_games, ROUND(AVG(price_final),2) AS avg_price, ROUND(AVG(positive_ratio),2) AS avg_positive_ratio FROM steam.games",
        "users": "SELECT COUNT(*) AS total_users, ROUND(AVG(products),2) AS avg_products, ROUND(AVG(reviews),2) AS avg_reviews, MAX(reviews) AS max_reviews FROM steam.users",
        "recommendations": "SELECT COUNT(*) AS total_recommendations, COUNT(*) FILTER (WHERE is_recommended IS TRUE) AS positive_recommendations, ROUND(100.0*COUNT(*) FILTER (WHERE is_recommended IS TRUE)/NULLIF(COUNT(*) FILTER (WHERE is_recommended IS NOT NULL),0),2) AS positive_pct, ROUND(AVG(hours),2) AS avg_hours FROM steam.recommendations",
        "tags": "SELECT COUNT(*) AS total_tags FROM steam.tags",
        "game_tags": "SELECT COUNT(*) AS total_links, COUNT(DISTINCT app_id) AS tagged_games, COUNT(DISTINCT tag_id) AS used_tags FROM steam.game_tags",
        "platforms": "SELECT COUNT(*) AS total_platforms FROM steam.platforms",
        "game_platforms": "SELECT COUNT(*) AS total_links, COUNT(DISTINCT app_id) AS covered_games, COUNT(DISTINCT platform_id) AS used_platforms FROM steam.game_platforms",
    }
    if chosen == 'recommendations':
        st.warning("Recommendations contains many rows. The exact SQL summary may take time; run it only when needed.")
    if st.button("Calculate exact SQL summary", key=f"summary_{chosen}", type="primary"):
        with st.spinner("Computing metrics in PostgreSQL..."):
            try:
                st.session_state[f"summary_result_{chosen}"] = read_sql(summary_sql[chosen])
            except Exception as exc:
                st.error(f"Unable to calculate summary: {exc}")
    if st.session_state.get(f"summary_result_{chosen}"):
        row = st.session_state[f"summary_result_{chosen}"][0]
        metric_cols = st.columns(min(len(row), 4))
        for i, (label, value) in enumerate(row.items()):
            metric_cols[i % len(metric_cols)].metric(label.replace('_', ' ').title(), num(value, 2) if isinstance(value, Decimal) else num(value))

    tab1, tab2 = st.tabs(["Row preview", "Column definitions"])
    with tab1:
        try:
            rows = read_sql(f'SELECT * FROM steam."{chosen}" LIMIT %s', (limit,))
            show_table(rows, height=330)
        except Exception as exc:
            st.error(f"Preview failed: {exc}")
    with tab2:
        show_table(columns, height=330)


def analytics():
    st.markdown('<div class="section-title">Live game analytics</div>', unsafe_allow_html=True)
    st.markdown('<p class="small-hint">Filters go directly into parameterized PostgreSQL queries. All aggregation happens in SQL.</p>', unsafe_allow_html=True)
    low, high = year_bounds()
    ratings, platforms = filter_options()
    with st.container(border=True):
        a, b, c = st.columns([2.3, 1.3, 1.3])
        with a:
            years = st.slider("Release year", min_value=low, max_value=high, value=(low, high)) if low < high else (low, high)
        with b:
            rating = st.selectbox("Rating category", ["All ratings"] + ratings)
        with c:
            platform = st.selectbox("Platform", ["All platforms"] + platforms)
        a2, b2 = st.columns(2)
        with a2:
            pricing = st.selectbox("Pricing", ["All prices", "Paid games", "Free games"])
        with b2:
            min_reviews = st.number_input("Minimum user reviews", min_value=0, max_value=10_000_000, value=100, step=100)

    where, params = build_game_conditions(years, rating, platform, pricing, min_reviews)
    with st.spinner("Retrieving filtered results from PostgreSQL..."):
        summary = read_sql(f"""
            SELECT COUNT(*) AS total_games, ROUND(AVG(g.price_final),2) AS avg_price,
                   ROUND(AVG(g.positive_ratio),2) AS avg_positive_ratio,
                   COUNT(*) FILTER (WHERE g.price_final=0) AS free_games
            FROM steam.games AS g WHERE {where}
        """, params)[0]
        cols = st.columns(4)
        cols[0].metric("Matching games", num(summary['total_games']))
        cols[1].metric("Average price", f"${num(summary['avg_price'],2)}" if summary['avg_price'] is not None else '—')
        cols[2].metric("Avg. positive reviews", f"{num(summary['avg_positive_ratio'],1)}%" if summary['avg_positive_ratio'] is not None else '—')
        cols[3].metric("Free games", num(summary['free_games']))

        rating_data = read_sql(f"""
            SELECT g.rating, COUNT(*) AS games
            FROM steam.games AS g
            WHERE {where} AND g.rating IS NOT NULL
            GROUP BY g.rating ORDER BY games DESC, g.rating
        """, params)
        platform_data = read_sql(f"""
            SELECT p.platform_name, COUNT(DISTINCT g.app_id) AS games
            FROM steam.games AS g
            JOIN steam.game_platforms AS gp ON gp.app_id = g.app_id
            JOIN steam.platforms AS p ON p.platform_id = gp.platform_id
            WHERE {where}
            GROUP BY p.platform_name ORDER BY games DESC, p.platform_name
        """, params)
        tag_data = read_sql(f"""
            SELECT t.tag_name, COUNT(DISTINCT g.app_id) AS games
            FROM steam.games AS g
            JOIN steam.game_tags AS gt ON gt.app_id = g.app_id
            JOIN steam.tags AS t ON t.tag_id = gt.tag_id
            WHERE {where}
            GROUP BY t.tag_id, t.tag_name
            ORDER BY games DESC, t.tag_name LIMIT 12
        """, params)
        top_data = read_sql(f"""
            SELECT g.title, g.positive_ratio, g.user_reviews, g.price_final
            FROM steam.games AS g
            WHERE {where} AND g.positive_ratio IS NOT NULL
            ORDER BY g.positive_ratio DESC, g.user_reviews DESC NULLS LAST, g.title, g.app_id
            LIMIT 15
        """, params)

    left, right = st.columns(2, gap='large')
    with left:
        st.markdown('<div class="section-title">Rating categories</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Bar(x=[x['rating'] for x in rating_data], y=[x['games'] for x in rating_data], marker_color=BLUE))
        fig.update_layout(xaxis_title=None, yaxis_title="Games")
        st.plotly_chart(plot_style(fig), use_container_width=True)
    with right:
        st.markdown('<div class="section-title">Platform compatibility</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Bar(x=[x['platform_name'] for x in platform_data], y=[x['games'] for x in platform_data], marker_color=GREEN))
        fig.update_layout(xaxis_title=None, yaxis_title="Games", showlegend=False)
        st.plotly_chart(plot_style(fig), use_container_width=True)
    left, right = st.columns(2, gap='large')
    with left:
        st.markdown('<div class="section-title">Top tags</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Bar(y=[r['tag_name'] for r in reversed(tag_data)], x=[r['games'] for r in reversed(tag_data)], orientation='h', marker_color="#4b91b6"))
        fig.update_layout(xaxis_title="Games", yaxis_title=None)
        st.plotly_chart(plot_style(fig, 450), use_container_width=True)
    with right:
        st.markdown('<div class="section-title">Highest-rated games</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Bar(y=[r['title'][:35] for r in reversed(top_data[:10])], x=[r['positive_ratio'] for r in reversed(top_data[:10])], orientation='h', marker_color="#77b8d8", customdata=[[r['user_reviews']] for r in reversed(top_data[:10])], hovertemplate='%{y}<br>Positive: %{x}%<br>Reviews: %{customdata[0]}<extra></extra>'))
        fig.update_layout(xaxis_title="Positive ratio (%)", yaxis_title=None)
        fig.update_xaxes(range=[0,100])
        st.plotly_chart(plot_style(fig, 450), use_container_width=True)
    with st.expander("Show filtered game table"):
        show_table(top_data, height=360)

    st.markdown('<div class="section-title">Recommendations over time</div>', unsafe_allow_html=True)
    st.caption("This section uses review dates, not game release dates. Months are grouped inside PostgreSQL.")
    with st.container(border=True):
        yr = read_sql("SELECT EXTRACT(YEAR FROM MIN(review_date))::INT AS lo, EXTRACT(YEAR FROM MAX(review_date))::INT AS hi FROM steam.recommendations WHERE review_date IS NOT NULL")[0]
        mn, mx = int(yr['lo'] or 2000), int(yr['hi'] or date.today().year)
        c1, c2 = st.columns([2, 1])
        with c1:
            review_years = st.slider("Review years", min_value=mn, max_value=mx, value=(max(mn, mx-5), mx), key="review_year") if mn < mx else (mn,mx)
        with c2:
            minimum_monthly = st.number_input("Min. reviews per month", min_value=1, value=100, step=100)
    if st.button("Load recommendation trends", type="primary"):
        try:
            with st.spinner("Analyzing recommendations in SQL..."):
                st.session_state['trend'] = read_sql("""
                    WITH monthly AS (
                      SELECT DATE_TRUNC('month',review_date)::DATE AS review_month,
                             COUNT(*) AS total_reviews,
                             COUNT(*) FILTER (WHERE is_recommended IS TRUE) AS positives,
                             ROUND(100.0 * COUNT(*) FILTER (WHERE is_recommended IS TRUE)/NULLIF(COUNT(*),0),2) AS positive_pct
                      FROM steam.recommendations
                      WHERE review_date >= MAKE_DATE(%s,1,1)
                        AND review_date < MAKE_DATE(%s+1,1,1)
                        AND is_recommended IS NOT NULL
                      GROUP BY DATE_TRUNC('month',review_date)::DATE
                      HAVING COUNT(*) >= %s
                    )
                    SELECT review_month, total_reviews, positives, positive_pct,
                           ROUND(positive_pct - LAG(positive_pct) OVER (ORDER BY review_month),2) AS change_pp
                    FROM monthly ORDER BY review_month
                """, (review_years[0], review_years[1], minimum_monthly))
                st.session_state['trend_filters'] = (review_years, minimum_monthly)
        except Exception as exc:
            st.error(f"Unable to load trend: {exc}")
    if 'trend' in st.session_state:
        if st.session_state.get('trend_filters') != (review_years, minimum_monthly):
            st.info("The filters have changed. Click 'Load recommendation trends' to refresh this chart.")
        data = st.session_state['trend']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[r['review_month'] for r in data], y=[r['positive_pct'] for r in data], name='Positive reviews', mode='lines+markers', line=dict(color=BLUE, width=3), marker=dict(size=5)))
        fig.update_layout(xaxis_title=None, yaxis_title="Positive recommendations (%)")
        st.plotly_chart(plot_style(fig, 350, percent=True), use_container_width=True)
        with st.expander('View monthly SQL results'):
            show_table(data)
    else:
        st.info("Click 'Load recommendation trends' to run the large-table query on demand.")

    st.markdown('<div class="section-title">Review behavior</div>', unsafe_allow_html=True)
    if st.button("Compare review playtime"):
        with st.spinner("Querying recommendations..."):
            st.session_state['playtime'] = read_sql("""
                SELECT CASE WHEN is_recommended THEN 'Positive' ELSE 'Negative' END AS sentiment,
                       COUNT(*) AS reviews, ROUND(AVG(hours),2) AS avg_hours,
                       ROUND(AVG(helpful),2) AS avg_helpful
                FROM steam.recommendations
                WHERE is_recommended IS NOT NULL AND hours IS NOT NULL
                GROUP BY is_recommended ORDER BY is_recommended DESC
            """)
    if 'playtime' in st.session_state:
        data = st.session_state['playtime']
        fig = go.Figure(go.Bar(x=[r['sentiment'] for r in data], y=[r['avg_hours'] for r in data], marker_color=[GREEN, '#e07a70'][:len(data)]))
        fig.update_layout(xaxis_title=None, yaxis_title="Average hours played")
        st.plotly_chart(plot_style(fig, 320), use_container_width=True)
        show_table(data, 160)


def sql_explorer():
    st.markdown('<div class="section-title">SQL query library</div>', unsafe_allow_html=True)
    st.caption("The 10 SQL files from your sql/ folder. Source files are displayed unmodified; Q9 has an optional performance-optimized execution mode. Q10 always rolls back.")
    items = [f"Q{i} · {name} ({tier})" for i, (_, name, tier) in enumerate(QUERIES,1)]
    choice = st.selectbox('Choose a query', range(len(QUERIES)), format_func=lambda ix: items[ix])
    filename, name, tier = QUERIES[choice]
    path = SQL_DIR / filename
    if path.is_file():
        st.code(path.read_text(encoding='utf-8'), language='sql')
    else:
        st.warning(f"File not found: sql/{filename}. Check the filename against your workspace.")
    if choice == 8:
        faster = st.checkbox("Run performance-optimized Q9 (CTE)", value=True)
        if faster:
            with st.expander('SQL executed in optimized mode'):
                st.code(OPTIMIZED_Q9, language='sql')
    else:
        faster = False
    if choice == 9:
        st.info('Q10 is a real UPDATE inside a transaction. The simulation uses RETURNING and guarantees ROLLBACK; it never saves changed prices.')
    if st.button('Execute selected query', type='primary'):
        try:
            with st.spinner('Running SQL on PostgreSQL...'):
                if choice == 9:
                    rows = simulate_discount()
                elif choice == 8 and faster:
                    rows = run_local_sql(OPTIMIZED_Q9)
                elif path.is_file():
                    rows = run_local_sql(path.read_text(encoding='utf-8'))
                else:
                    st.error('SQL file missing; cannot run this query.')
                    return
                st.session_state['query_output'] = (choice, rows)
        except Exception as exc:
            st.error(f"Query failed: {exc}")
    result = st.session_state.get('query_output')
    if result is not None and result[0] == choice:
        st.success(f"Query executed. {len(result[1])} rows returned.")
        show_table(result[1], 440)
        if result[1]:
            st.download_button('Download result as CSV', data=rows_to_csv(result[1]), file_name=f'q{choice+1}_results.csv', mime='text/csv')


def rows_to_csv(rows: list[dict]) -> str:
    import csv
    import io
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


st.markdown('''<div class="hero"><div class="kicker">STEAM / DATA INTELLIGENCE</div>
<h1>STEAM INSIGHTS <span style="color:#66c0f4">//</span> PROJECT B</h1>
<p>Explore the Steam ecosystem · PostgreSQL relational data · Live SQL-powered visualizations</p></div>''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('### 🎮 STEAM INSIGHTS')
    st.caption('INFORMATION TECHNOLOGY · PROJECT B')
    st.divider()
    st.markdown('**Data source**')
    st.caption('Steam game recommendations dataset')
    st.markdown('**Database**')
    st.code('steam_db  /  schema: steam', language=None)
    st.caption('All filters are safely parameterized; numerical analyses run in PostgreSQL.')
    if st.button('Refresh cached data'):
        read_sql.clear()
        table_registry.clear()
        column_registry.clear()
        year_bounds.clear()
        filter_options.clear()
        st.rerun()
    st.divider()
    st.caption('The dashboard is an independent academic visualization, not an official Steam product.')

try:
    connected = read_sql('SELECT CURRENT_DATABASE() AS db, CURRENT_SCHEMA() AS active_schema, version() AS version')[0]
except Exception as exc:
    st.error('Could not connect to PostgreSQL. Confirm steam_db is available, scripts/db_conn.py uses dbname=dbname, and password.txt is in the project root.')
    st.exception(exc)
    st.stop()

st.caption(f"● Connected to {html.escape(str(connected['db']))} · SQL-backed dashboard")
section = st.radio('Dashboard section', ['📊 Data Overview', '📈 Analytics', '🧪 SQL Explorer'], horizontal=True, label_visibility='collapsed')
if section == '📊 Data Overview':
    home_overview()
elif section == '📈 Analytics':
    analytics()
else:
    sql_explorer()
