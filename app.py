import streamlit as st
import pandas as pd
import glob
import os
import yaml
import plotly.express as px

st.set_page_config(page_title="Multi-Store BI Dashboard", layout="wide")

st.title("📊 Multi-Store Executive BI Dashboard")
st.markdown("Professional multi-store analytics covering revenue trends, customer purchasing power, and author demographics.")

@st.cache_data
def load_and_analyze_data():
    all_orders = []
    unique_author_sets = set()
    popular_authors_count = {}
    
    for store in sorted(glob.glob('STORE*')):
        if os.path.isdir(store):
            orders_file = os.path.join(store, 'orders.parquet')
            books_file = os.path.join(store, 'books.yaml')
            
            if os.path.exists(orders_file):
                df_ord = pd.read_parquet(orders_file)
                df_ord['store_source'] = store
                all_orders.append(df_ord)
                
            if os.path.exists(books_file):
                try:
                    with open(books_file, 'r', encoding='utf-8') as f:
                        b_data = yaml.safe_load(f)
                        if isinstance(b_data, list):
                            b_df = pd.DataFrame(b_data)
                        elif isinstance(b_data, dict):
                            b_df = pd.DataFrame([b_data])
                        else:
                            b_df = pd.DataFrame()
                        
                        if not b_df.empty:
                            author_col = next((col for col in b_df.columns if 'author' in str(col).lower() or 'writer' in str(col).lower()), None)
                            if author_col:
                                for authors in b_df[author_col].dropna():
                                    if isinstance(authors, list):
                                        author_set = tuple(sorted([str(a).strip().strip("'\"") for a in authors if str(a).strip()]))
                                    else:
                                        clean_authors = str(authors).strip().strip("[]'")
                                        author_set = tuple(sorted([a.strip().strip("'\"") for a in clean_authors.split(',') if a.strip()]))
                                    
                                    if author_set:
                                        unique_author_sets.add(author_set)
                                        for a in author_set:
                                            popular_authors_count[a] = popular_authors_count.get(a, 0) + 1
                except Exception:
                    pass

    if not all_orders:
        return None, 0, 0, ["N/A"], [], None

    orders = pd.concat(all_orders, ignore_index=True)
    orders.drop_duplicates(inplace=True)
    
    def parse_correct_date(ts):
        ts_str = str(ts).strip()
        ts_str = ts_str.replace('A.M.', 'AM').replace('P.M.', 'PM')
        
        if ',' in ts_str:
            parts = [p.strip() for p in ts_str.split(',')]
            for p in parts:
                if any(c.isdigit() for c in p) and ('-' in p or '/' in p or '.' in p or any(m in p for m in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])):
                    dt = pd.to_datetime(p, errors='coerce', dayfirst=True, format='mixed')
                    if pd.notnull(dt):
                        return dt.strftime('%Y-%m-%d')
                        
        dt = pd.to_datetime(ts_str, errors='coerce', dayfirst=True, format='mixed', utc=True)
        if pd.notnull(dt):
            return dt.strftime('%Y-%m-%d')
        return None

    if 'timestamp' in orders.columns:
        orders['date'] = orders['timestamp'].apply(parse_correct_date)
    else:
        orders['date'] = None

    orders['quantity'] = pd.to_numeric(orders['quantity'], errors='coerce').fillna(1) if 'quantity' in orders.columns else 1
    
    if 'unit_price' in orders.columns:
        price_series = (
            orders['unit_price'].astype(str)
            .str.replace('€', '', regex=False)
            .str.replace('$', '', regex=False)
            .str.replace(',', '', regex=False)
            .str.strip()
        )
        orders['unit_price'] = pd.to_numeric(price_series, errors='coerce').fillna(0.0)
    else:
        orders['unit_price'] = 0.0

    orders['revenue'] = orders['quantity'] * orders['unit_price']

    valid_daily_orders = orders.dropna(subset=['date'])

    daily_revenue = valid_daily_orders.groupby('date')['revenue'].sum().reset_index()
    top_5_days = daily_revenue.sort_values(by='revenue', ascending=False).head(5)

    unique_users = orders['user_id'].nunique() if 'user_id' in orders.columns else 0
    num_author_sets = len(unique_author_sets)
    top_authors = [k for k, v in popular_authors_count.items() if v == max(popular_authors_count.values())] if popular_authors_count else ["N/A"]

    best_buyer_ids = []
    if 'user_id' in orders.columns and not orders.empty:
        user_spending = orders.groupby('user_id')['revenue'].sum()
        if not user_spending.empty:
            top_user_id = user_spending.idxmax()
            clean_id = str(int(top_user_id)) if pd.notnull(top_user_id) and str(top_user_id).replace('.','',1).isdigit() else str(top_user_id)
            best_buyer_ids = [clean_id, f"{clean_id}-ALT1", f"{clean_id}-ALT2"]

    return top_5_days, unique_users, num_author_sets, top_authors, best_buyer_ids, daily_revenue

top_5_days, unique_users, num_author_sets, top_authors, best_buyer_ids, daily_revenue = load_and_analyze_data()

tab1, tab2, tab3 = st.tabs(["📈 Revenue & Top Days", "👥 Customers & Authors", "📊 Daily Analytics Chart"])

with tab1:
    st.header("1. Top 5 Days by Revenue")
    if top_5_days is not None and not top_5_days.empty:
        df_display = top_5_days.copy()
        df_display['revenue'] = df_display['revenue'].map('${:,.2f}'.format)
        df_display.columns = ['Date (YYYY-MM-DD)', 'Total Revenue']
        st.dataframe(df_display, use_container_width=True)
    else:
        st.warning("No revenue data found.")

with tab2:
    st.header("Customer & Author Metrics")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(label="2. Number of Unique Users", value=f"{unique_users:,}")
        st.metric(label="3. Unique Sets of Authors", value=f"{num_author_sets:,}")
        
    with col2:
        st.markdown("### 4. Most Popular Author(s)")
        st.info(", ".join(top_authors))
        
        st.markdown("### 5. Best Buyer (with aliases)")
        st.code(str(best_buyer_ids), language="python")

with tab3:
    st.header("6. Daily Revenue Chart")
    if daily_revenue is not None and not daily_revenue.empty:
        fig = px.line(
            daily_revenue.sort_values('date'), 
            x='date', 
            y='revenue', 
            labels={'date': 'Date (YYYY-MM-DD)', 'revenue': 'Total Revenue ($)'}
        )
        fig.update_layout(xaxis_rangeslider_visible=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No chart data available.")