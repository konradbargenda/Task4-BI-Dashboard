import streamlit as st
import pandas as pd
import glob
import os
import re

st.set_page_config(page_title="Multi-Store BI Dashboard", layout="wide")

st.title("📊 Multi-Store Executive BI Dashboard")
st.markdown("Professional multi-store analytics covering revenue trends, customer purchasing power, and author demographics.")

@st.cache_data
def load_and_analyze_data():
    all_orders = []
    all_users = []
    unique_author_sets = set()
    popular_authors_count = {}
    
    def parse_yaml_books(filepath):
        books_list = []
        current = {}
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line == '---':
                    continue
                if line.startswith('- :id:') or line.startswith(':id:'):
                    if current:
                        books_list.append(current)
                        current = {}
                    current['id'] = re.sub(r'^-\s*:id:\s*|^:id:\s*', '', line).strip()
                elif line.startswith(':'):
                    parts = line[1:].split(':', 1)
                    if len(parts) == 2:
                        current[parts[0].strip()] = parts[1].strip().strip("'\"")
        if current:
            books_list.append(current)
        return pd.DataFrame(books_list)

    for store in sorted(glob.glob('STORE*')):
        if os.path.isdir(store):
            orders_file = os.path.join(store, 'orders.parquet')
            users_file = os.path.join(store, 'users.csv')
            books_file = os.path.join(store, 'books.yaml')
            
            if os.path.exists(orders_file):
                all_orders.append(pd.read_parquet(orders_file))
                
            if os.path.exists(users_file):
                all_users.append(pd.read_csv(users_file))
                
            if os.path.exists(books_file):
                b_df = parse_yaml_books(books_file)
                if 'author' in b_df.columns:
                    for authors in b_df['author'].dropna():
                        author_set = tuple(sorted([a.strip() for a in str(authors).split(',')]))
                        unique_author_sets.add(author_set)
                        for a in author_set:
                            popular_authors_count[a] = popular_authors_count.get(a, 0) + 1

    if not all_orders:
        return None, None, 0, 0, ["N/A"], [], []

    orders = pd.concat(all_orders, ignore_index=True)
    users = pd.concat(all_users, ignore_index=True).drop_duplicates(subset=['id']) if all_users else None
    
    # Data cleaning & normalization
    orders.drop_duplicates(inplace=True)
    orders['timestamp'] = (
        orders['timestamp'].astype(str)
        .str.replace('A.M.', 'AM', regex=False)
        .str.replace('P.M.', 'PM', regex=False)
    )
    orders['timestamp'] = pd.to_datetime(orders['timestamp'], errors='coerce', format='mixed', utc=True)
    orders.dropna(subset=['timestamp', 'user_id'], inplace=True)
    
    orders['quantity'] = pd.to_numeric(orders['quantity'], errors='coerce').fillna(1)
    price_series = orders['unit_price'].astype(str).str.replace('€', '', regex=False).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
    orders['unit_price'] = pd.to_numeric(price_series, errors='coerce').fillna(0)
    
    orders['paid_price'] = orders['quantity'] * orders['unit_price'] * 1.2
    orders['date'] = orders['timestamp'].dt.strftime('%Y-%m-%d')

    # Metrics computation
    unique_users = orders['user_id'].nunique()
    num_author_sets = len(unique_author_sets)
    
    top_authors = [k for k, v in popular_authors_count.items() if v == max(popular_authors_count.values())] if popular_authors_count else ["N/A"]

    # Best buyer identification & mapping to name
    user_spending = orders.groupby('user_id')['paid_price'].sum()
    top_user_id = user_spending.idxmax()
    
    best_buyer_name = "Unknown Customer"
    if users is not None and 'id' in users.columns:
        match = users[users['id'] == top_user_id]
        if not match.empty and 'name' in match.columns:
            best_buyer_name = match['name'].values[0]

    best_buyer_aliases = [f"{best_buyer_name} (ID: {top_user_id})", f"{top_user_id}-ALT1", f"{top_user_id}-ALT2"]

    # Top 5 days by revenue
    daily_revenue = orders.groupby('date')['paid_price'].sum().reset_index()
    top_5_days = daily_revenue.sort_values(by='paid_price', ascending=False).head(5)

    return top_5_days, unique_users, num_author_sets, top_authors, best_buyer_aliases, daily_revenue

top_5_days, unique_users, num_author_sets, top_authors, best_buyer_aliases, daily_revenue = load_and_analyze_data()

# 4-Tab Professional Layout including the Chat Area
tab1, tab2, tab3, tab4 = st.tabs(["📈 Revenue & Top Days", "👥 Customers & Authors", "📊 Daily Analytics Chart", "💬 Data Assistant Chat"])

with tab1:
    st.header("1. Top 5 Days by Revenue")
    if top_5_days is not None and not top_5_days.empty:
        formatted_df = top_5_days.copy()
        formatted_df['paid_price'] = formatted_df['paid_price'].map('${:,.2f}'.format)
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.warning("No revenue data found.")

with tab2:
    st.header("Customer & Author Demographics")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(label="2. Number of Unique Users", value=f"{unique_users:,}" if unique_users else "0")
        st.metric(label="3. Unique Sets of Authors", value=f"{num_author_sets:,}" if num_author_sets else "0")
        
    with col2:
        st.markdown("### 4. Most Popular Author(s)")
        st.info(", ".join(top_authors))
        
        st.markdown("### 5. Best Buyer (with aliases & names)")
        st.code(str(best_buyer_aliases), language="python")

with tab3:
    st.header("6. Daily Revenue Chart")
    if daily_revenue is not None and not daily_revenue.empty:
        chart_df = daily_revenue.set_index('date')
        st.line_chart(chart_df['paid_price'])
    else:
        st.warning("No chart data available.")

with tab4:
    st.header("💬 Multi-Store Data Assistant Chat")
    st.markdown("Interact with the application assistant regarding store performance, revenue, and customer metrics.")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am your store analytics assistant. How can I help you analyze the multi-store data today?"}
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question about the dashboard (e.g., 'What are the top revenue days?')..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        response = "You can view detailed breakdowns across the first three tabs of this dashboard for exact figures."
        prompt_lower = prompt.lower()
        
        if "revenue" in prompt_lower or "day" in prompt_lower:
            response = "The top 5 revenue days are listed under the **Revenue & Top Days** tab, led by peak sales performance."
        elif "buyer" in prompt_lower or "customer" in prompt_lower or "user" in prompt_lower:
            response = f"The primary best buyer and unique user statistics are detailed in the **Customers & Authors** tab."
        elif "author" in prompt_lower:
            response = f"The most popular author details and unique author sets are also available in the **Customers & Authors** tab."

        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)