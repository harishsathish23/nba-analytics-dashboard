import streamlit as st
import pandas as pd

def render_simulator_tab(df, player_name, player_stats, base_projection):
    """
    Renders the 'Trade Simulator' tab content with Multi-Player support.
    """
    col_controls, col_results = st.columns([1, 1.5])
    
    with col_controls:
        st.subheader("Trade Scenario")
        
        # 1. IDENTIFY LISTS
        # Teammates (for removal)
        team_id = player_stats['TEAM_ID']
        teammates = df[df['TEAM_ID'] == team_id]
        teammates = teammates[teammates['PLAYER_NAME'] != player_name]
        
        # All Players (for addition) - Exclude current teammates and self
        current_roster_names = set(teammates['PLAYER_NAME'].unique())
        current_roster_names.add(player_name)
        
        available_free_agents = df[~df['PLAYER_NAME'].isin(current_roster_names)]
        
        # 2. CONTROLS (MultiSelect)
        remove_players = st.multiselect(
            "🔴 Remove Teammates (Outgoing):", 
            options=list(teammates['PLAYER_NAME'].sort_values().unique()),
            default=[]
        )
        
        add_players = st.multiselect(
            "🟢 Add Players (Incoming):", 
            options=list(available_free_agents['PLAYER_NAME'].sort_values().unique()),
            default=[]
        )
        
        # 3. CALCULATE NET VOLUME
        net_vacant_fga = 0.0
        outgoing_desc = []
        incoming_desc = []
        
        # Add volume from ALL leaving players
        if remove_players:
            leaving_stats_df = teammates[teammates['PLAYER_NAME'].isin(remove_players)]
            total_leaving_fga = leaving_stats_df['FGA'].sum()
            net_vacant_fga += total_leaving_fga
            
            for _, row in leaving_stats_df.iterrows():
                outgoing_desc.append(f"{row['PLAYER_NAME']} ({row['FGA']:.1f})")
            
        # Subtract volume from ALL incoming players
        if add_players:
            incoming_stats_df = available_free_agents[available_free_agents['PLAYER_NAME'].isin(add_players)]
            total_incoming_fga = incoming_stats_df['FGA'].sum()
            net_vacant_fga -= total_incoming_fga
            
            for _, row in incoming_stats_df.iterrows():
                incoming_desc.append(f"{row['PLAYER_NAME']} ({row['FGA']:.1f})")
            
        # 4. DYNAMIC SLIDER
        if net_vacant_fga > 0:
            slider_label = "Usage Absorption %"
            slider_help = f"Surplus of {net_vacant_fga:.1f} shots available. What % does {player_name} absorb?"
            slider_color = "green"
        elif net_vacant_fga < 0:
            slider_label = "Usage Sacrifice %"
            slider_help = f"Deficit of {abs(net_vacant_fga):.1f} shots. What % does {player_name} give up?"
            slider_color = "red"
        else:
            slider_label = "Impact Share %"
            slider_help = "No net change in shot volume."
            slider_color = "gray"

        impact_share = st.slider(
            slider_label, 
            min_value=0, 
            max_value=50, 
            value=15, 
            step=1,
            format="%d%%",
            help=slider_help
        )
        
        # Convert to decimal
        share_rate = impact_share / 100.0
        
        # Show Volume Reflection
        if remove_players or add_players:
            volume_change = net_vacant_fga * share_rate
            if volume_change > 0:
                st.caption(f"📈 **Projection:** {player_name} gains +{volume_change:.1f} FGA")
            elif volume_change < 0:
                st.caption(f"📉 **Projection:** {player_name} loses {volume_change:.1f} FGA")
            else:
                st.caption("No significant volume change.")

    with col_results:
        st.subheader("Projected Impact")
        
        final_pts = base_projection['PTS']
        final_ast = base_projection['AST']
        final_reb = base_projection['REB']
        
        impact_msg = "No scenario active. Showing Age-Adjusted Baseline."
        
        if remove_players or add_players:
            # Apply the net change
            volume_change = net_vacant_fga * share_rate
            
            # Points Calculation
            efficiency_multiplier = 1.2 if volume_change > 0 else 1.1
            points_change = volume_change * efficiency_multiplier
            final_pts += points_change
            
            # Assists Calculation
            final_ast += (volume_change * 0.2)
            
            # Build the Scenario Message
            msg_lines = []
            if outgoing_desc:
                msg_lines.append(f"**Leaving:** {', '.join(outgoing_desc)}")
            if incoming_desc:
                msg_lines.append(f"**Joining:** {', '.join(incoming_desc)}")
            
            scenario_text = "\n\n".join(msg_lines)
            
            impact_msg = (
                f"{scenario_text}\n\n"
                f"**Net Team Volume:** {net_vacant_fga:+.1f} Shots\n\n"
                f"**{player_name} Impact:** {volume_change:+.1f} FGA ({impact_share}% share)"
            )
        
        if net_vacant_fga < 0:
            st.warning(impact_msg)
        else:
            st.success(impact_msg)
        
        # Big Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Projected Points", f"{final_pts:.1f}", delta=f"{final_pts - player_stats['PTS']:.1f}")
        m2.metric("Projected Assists", f"{final_ast:.1f}", delta=f"{final_ast - player_stats['AST']:.1f}")
        m3.metric("Projected Rebounds", f"{final_reb:.1f}", delta=f"{final_reb - player_stats['REB']:.1f}")
        
        # Visual Comparison
        st.markdown("---")
        st.markdown("#### Stat Breakdown")
        comp_data = {
            "Stat": ["Points", "Assists", "Rebounds"],
            "Last Season": [player_stats['PTS'], player_stats['AST'], player_stats['REB']],
            "Base Projection (Age Only)": [base_projection['PTS'], base_projection['AST'], base_projection['REB']],
            "Trade Scenario": [final_pts, final_ast, final_reb]
        }
        st.dataframe(
            pd.DataFrame(comp_data).set_index("Stat").style.format("{:.1f}"), 
            use_container_width=True
        )

    # *** BLURB MOVED TO BOTTOM ***
    st.markdown("---")
    st.info(
        "How will this player's statline be impacted given a potential trade? "
        "This factors in the usage of the players being added and subtracted from the roster "
        "and gives you the ability to step in and tweak how this trade impacts the player's usage."
    )