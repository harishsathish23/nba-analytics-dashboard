import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from nba_api.stats.endpoints import leaguedashplayerstats, playercareerstats
from datetime import datetime
import simulator 

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="NBA Analytics Dashboard")

st.title("NBA Analytics Dashboard") 

# --- 1. DATA LOADING ---
@st.cache_data(ttl=3600)
def get_nba_data(season):
    with st.spinner(f"Fetching Pro Stats for {season}..."):
        try:
            base_pg = leaguedashplayerstats.LeagueDashPlayerStats(season=season, per_mode_detailed='PerGame', measure_type_detailed_defense='Base').get_data_frames()[0]
            base_p36 = leaguedashplayerstats.LeagueDashPlayerStats(season=season, per_mode_detailed='Per36', measure_type_detailed_defense='Base').get_data_frames()[0]
            adv = leaguedashplayerstats.LeagueDashPlayerStats(season=season, measure_type_detailed_defense='Advanced').get_data_frames()[0]

            base_p36 = base_p36[['PLAYER_ID', 'PTS', 'STL', 'BLK']]
            base_p36.columns = ['PLAYER_ID', 'PTS_36', 'STL_36', 'BLK_36']
            adv = adv[['PLAYER_ID', 'TS_PCT', 'EFG_PCT', 'AST_PCT', 'OREB_PCT', 'DREB_PCT']]
            
            df = pd.merge(base_pg, base_p36, on='PLAYER_ID')
            df = pd.merge(df, adv, on='PLAYER_ID')
            df['FTr'] = df['FTA'] / df['FGA'].replace(0, 1)
            return df
        except Exception as e:
            st.error(f"Error fetching NBA data: {e}")
            return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_career_stats(player_id):
    try:
        df = playercareerstats.PlayerCareerStats(player_id=player_id).get_data_frames()[0]
        df['PPG'] = (df['PTS'] / df['GP']).round(1)
        df['APG'] = (df['AST'] / df['GP']).round(1)
        df['RPG'] = (df['REB'] / df['GP']).round(1)
        return df
    except:
        return pd.DataFrame()

# --- 2. SETUP & FILTERING ---
st.sidebar.header("Settings")
current_year = datetime.now().year
seasons = [f"{year}-{str(year+1)[-2:]}" for year in range(current_year, 2014, -1)]

default_season_index = 0
if "2023-24" in seasons:
    default_season_index = seasons.index("2023-24")

selected_season = st.sidebar.selectbox("Season", seasons, index=default_season_index)

df = get_nba_data(selected_season)
if df.empty: st.stop()

min_games = st.sidebar.slider("Min Games Played", 0, 82, 15)
df_filtered = df[df['GP'] >= min_games].copy()

# Metric Mapping
metrics_map = {
    'MIN': 'Minutes', 'PTS_36': 'PTS / 36', 'FTr': 'FT Rate',
    'TS_PCT': 'True Shooting %', 'EFG_PCT': 'eFG %', 'FG3_PCT': '3P %',
    'AST_PCT': 'Assist %', 'OREB_PCT': 'O-Reb %', 'DREB_PCT': 'D-Reb %',
    'STL_36': 'Steals / 36', 'BLK_36': 'Blocks / 36'
}
target_cols = list(metrics_map.keys())
percentile_df = df_filtered[target_cols].rank(pct=True) * 100

# --- 3. PLAYER SELECTION ---
st.sidebar.markdown("---")
comparison_mode = st.sidebar.checkbox("Compare Players", value=False)
player_list = df_filtered['PLAYER_NAME'].sort_values().unique()

if comparison_mode:
    p1_name = st.sidebar.selectbox("Player 1", player_list, index=0)
    p2_name = st.sidebar.selectbox("Player 2", player_list, index=1 if len(player_list) > 1 else 0)
else:
    default_player_index = 0
    player_list_list = player_list.tolist()
    if "Joel Embiid" in player_list_list:
        default_player_index = player_list_list.index("Joel Embiid")
        
    p1_name = st.sidebar.selectbox("Select Player", player_list, index=default_player_index)

# --- 4. HELPER FUNCTIONS ---
def get_player_data(name):
    stats = df_filtered[df_filtered['PLAYER_NAME'] == name].iloc[0]
    pcts = percentile_df.loc[stats.name]
    return stats, pcts

def format_value(col_name, val):
    if 'PCT' in col_name or 'Rate' in metrics_map.get(col_name, ''):
        return f"{val*100:.1f}%" if val < 1.0 else f"{val:.1f}%"
    elif 'FTr' in col_name:
        return f"{val:.3f}"
    else:
        return f"{val:.1f}"

def generate_projection(player_stats, age_factor=None):
    current_age = player_stats['AGE']
    if age_factor is None:
        if current_age < 26: age_factor = 1.03
        elif current_age <= 30: age_factor = 1.00
        else: age_factor = 0.95
    
    proj = {
        'PTS': player_stats['PTS'] * age_factor,
        'AST': player_stats['AST'] * age_factor,
        'REB': player_stats['REB'] * age_factor,
        'FGA': player_stats['FGA'] * age_factor,
    }
    return proj, age_factor

# --- 5. RENDER DASHBOARD ---
if not comparison_mode:
    stats, pcts = get_player_data(p1_name)
    career = get_career_stats(stats['PLAYER_ID'])
    
    st.header(f"🏀 {p1_name}")
    st.caption(f"{stats['TEAM_ABBREVIATION']} | {stats['GP']} GP | {stats['MIN']:.1f} MPG | Age: {int(stats['AGE'])}")
    
    tab_overview, tab_career, tab_sim = st.tabs(["Current Stats", "Career Trajectory", "Trade Simulator"])
    
    with tab_overview:
        col1, col2 = st.columns([1, 1.2])
        with col1:
            st.subheader("Skill Radar")
            fig_radar = go.Figure(go.Scatterpolar(
                r=pcts[target_cols].values,
                theta=[metrics_map[c] for c in target_cols],
                fill='toself', name=p1_name, line_color='#1d428a'
            ))
            
            # Hide radial numbers
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], showticklabels=False)
                ), 
                showlegend=False, 
                height=400
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with col2:
            st.subheader("Percentile Profile")
            bar_colors = ['#22c55e' if x >= 80 else '#ef4444' if x <= 20 else '#eab308' for x in pcts[target_cols].values]
            display_text = [format_value(c, stats[c]) for c in target_cols]
            
            fig_bar = go.Figure(go.Bar(
                x=pcts[target_cols].values[::-1],
                y=[metrics_map[c] for c in target_cols][::-1],
                orientation='h', marker_color=bar_colors[::-1],
                text=display_text[::-1], textposition='inside', insidetextanchor='end'
            ))
            
            fig_bar.update_layout(
                xaxis=dict(range=[0, 100], showticklabels=False), 
                height=400,
                margin=dict(l=0, r=0, t=20, b=20)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    with tab_career:
        st.subheader("📊 Career Progression")
        if not career.empty:
            # Create 3 columns for side-by-side graphs
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown("**Points Per Game**")
                fig_pts = go.Figure()
                fig_pts.add_trace(go.Scatter(
                    x=career['SEASON_ID'], y=career['PPG'], 
                    mode='lines+markers', name='Points', 
                    line=dict(color='#1d428a', width=3)
                ))
                fig_pts.update_layout(
                    hovermode="x unified", height=300, 
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis_title="PPG",
                    showlegend=False
                )
                st.plotly_chart(fig_pts, use_container_width=True)
            
            with c2:
                st.markdown("**Assists Per Game**")
                fig_ast = go.Figure()
                fig_ast.add_trace(go.Scatter(
                    x=career['SEASON_ID'], y=career['APG'], 
                    mode='lines+markers', name='Assists', 
                    line=dict(color='#eab308', width=3)
                ))
                fig_ast.update_layout(
                    hovermode="x unified", height=300, 
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis_title="APG",
                    showlegend=False
                )
                st.plotly_chart(fig_ast, use_container_width=True)

            with c3:
                st.markdown("**Rebounds Per Game**")
                fig_reb = go.Figure()
                fig_reb.add_trace(go.Scatter(
                    x=career['SEASON_ID'], y=career['RPG'], 
                    mode='lines+markers', name='Rebounds', 
                    line=dict(color='#ef4444', width=3)
                ))
                fig_reb.update_layout(
                    hovermode="x unified", height=300, 
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis_title="RPG",
                    showlegend=False
                )
                st.plotly_chart(fig_reb, use_container_width=True)
            
            base_proj, age_factor = generate_projection(stats)
            st.info(f"Based on Age {int(stats['AGE'])}, we project a **{age_factor}x** multiplier for next season.")
        else:
            st.warning("Career data unavailable.")

    with tab_sim:
        base_proj, _ = generate_projection(stats)
        simulator.render_simulator_tab(df, p1_name, stats, base_proj)

else:
    # COMPARISON MODE
    st.header(f"⚔️ {p1_name} vs {p2_name}")
    try:
        s1, p1 = get_player_data(p1_name)
        s2, p2 = get_player_data(p2_name)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("Skill Comparison")
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=p1[target_cols].values, theta=[metrics_map[c] for c in target_cols], fill='toself', name=p1_name, line_color='#1d428a', opacity=0.6))
            fig.add_trace(go.Scatterpolar(r=p2[target_cols].values, theta=[metrics_map[c] for c in target_cols], fill='toself', name=p2_name, line_color='#E03A3E', opacity=0.5))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], showticklabels=False)
                ), 
                showlegend=True, 
                legend=dict(orientation="h", y=1.1), 
                height=450
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.subheader("Head-to-Head Table")
            comp_rows = []
            for col in target_cols:
                comp_rows.append({
                    "Stat": metrics_map[col],
                    p1_name: format_value(col, s1[col]),
                    p2_name: format_value(col, s2[col]),
                    "Raw_Diff": s1[col] - s2[col] 
                })
            comp_df = pd.DataFrame(comp_rows).set_index("Stat")
            st.dataframe(comp_df[[p1_name, p2_name]], use_container_width=True, height=450)

    except Exception as e:
        st.error(f"Error in comparison: {e}")