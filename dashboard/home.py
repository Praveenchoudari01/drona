from dash import html, dcc
import pandas as pd
from sqlalchemy import create_engine
import plotly.graph_objs as go
import dash_bootstrap_components as dbc


def perform_analytics():
    # ✅ Database connection (replace with your actual credentials)
    engine = create_engine("mysql+pymysql://root:1619@localhost:3306/drona")
    
    # ✅ Query: Get Total Active Viewers
    query = "SELECT COUNT(*) AS total_viewers FROM viewer WHERE is_active = 1"
    df = pd.read_sql(query, con=engine)
    total_viewers = df['total_viewers'].iloc[0]


    # ✅ Query: Get Failure Percentage
    query = """
    SELECT 
        ROUND(
            (SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 
            2
        ) AS failure_percentage
    FROM viewer_session
    """
    df = pd.read_sql(query, con=engine)
    failure_percentage = df['failure_percentage'].iloc[0]

    # ✅ Query: Completed Trainings (Your query here)
    query = """
    SELECT SUM(completion_count) AS total_completions
    FROM (
        SELECT viewer_id, module_id, attempt_no, 
               COUNT(question_id) AS total_questions, 
               COUNT(level_id) AS total_levels,
               CASE 
                   WHEN module_id = 1 AND COUNT(question_id) >= 10 AND COUNT(level_id) >= 3 THEN 1
                   WHEN module_id = 2 AND COUNT(question_id) >= 16 AND COUNT(level_id) >= 6 THEN 1
                   ELSE 0
               END AS completion_count
        FROM viewer_answers
        GROUP BY viewer_id, module_id, attempt_no
    ) AS per_attempt
    WHERE completion_count = 1;
    """
    df = pd.read_sql(query, con=engine)
    certified_viewers = df['total_completions'].iloc[0]


    query = '''
        SELECT
    (
        SELECT SUM(total_sessions)

    FROM (
            SELECT 
                viewer_id,
                MAX(training_count) AS total_sessions
            FROM (
                SELECT 
                    viewer_id,
                    COUNT(DISTINCT training_session_id) AS training_count
                FROM viewer_session
                GROUP BY viewer_id
            ) AS per_viewer_module
            GROUP BY viewer_id
        ) AS viewer_max_sessions
    ) AS total_sessions,

    (
        SELECT COUNT(*)
        FROM viewer_session
        WHERE status = 'failed'
        AND last_module_id IN (1, 2)
    ) AS total_failures,

    (
        SELECT ROUND(
            (COUNT(*) * 100.0) / 
            (
                SELECT SUM(total_sessions)
                FROM (
                    SELECT 
                        viewer_id,
                        MAX(training_count) AS total_sessions
                    FROM (
                        SELECT 
                            viewer_id,
                            COUNT(DISTINCT training_session_id) AS training_count
                        FROM viewer_session
                        GROUP BY viewer_id
                    ) AS per_viewer_module
                    GROUP BY viewer_id
                ) AS viewer_max_sessions
            ), 2
        )
        FROM viewer_session
        WHERE status = 'success'
    ) AS success_percentage;    
    '''
    df = pd.read_sql(query, con=engine)
    total_traings = df['total_sessions'].iloc[0]

    # ✅ Module-wise Training Stats
    query = """
        SELECT 
            m.module_name,
            COUNT(vs.id) AS total_training_sessions,
            ROUND(
                (SUM(CASE WHEN vs.status = 'FAILED' THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(vs.id), 0), 
                2
            ) AS failed_percentage
        FROM module m
        LEFT JOIN viewer_session vs
        ON vs.last_module_id = m.id
        GROUP BY m.module_name;
    """
    module_stats = pd.read_sql(query, con=engine)
    module_stats['avg_time'] = '-'  # Placeholder column
    
    # ✅ Viewer-wise Latest Session Stats
    query = """
        SELECT 
            v.id AS viewer_id,
            v.name AS viewer_name,
            d.name AS department_name,
            m.module_name,
            vs.status,
            vs.score
        FROM viewer_session vs
        JOIN (
            SELECT viewer_id, MAX(id) AS latest_session_id
            FROM viewer_session
            GROUP BY viewer_id
        ) latest_vs 
            ON vs.viewer_id = latest_vs.viewer_id AND vs.id = latest_vs.latest_session_id
        JOIN viewer v 
            ON vs.viewer_id = v.id
        JOIN department d 
            ON v.department_id = d.id
        JOIN module m 
            ON vs.last_module_id = m.id
        LIMIT 5;

    """
    viewer_table = pd.read_sql(query, con=engine)
    viewer_table['score']='-'

    # Fetch Module-Wise Training Counts
    query = """
    SELECT 
        m.module_name,
        COUNT(vs.id) AS total_training_sessions
    FROM module m
    LEFT JOIN viewer_session vs 
        ON vs.last_module_id = m.id
    GROUP BY m.module_name;
    """
    module_training_counts = pd.read_sql(query, con=engine)

    failure_query = """
    SELECT 
        q.id AS question_id,
        q.question_abbr,
        COUNT(*) AS failure_count
    FROM viewer_answers va
    JOIN viewer_session vs 
        ON va.training_session_id = vs.training_session_id
    JOIN questions q 
        ON va.question_id = q.id
    WHERE vs.status = 'FAILED'
    GROUP BY q.id, q.question_abbr
    ORDER BY failure_count DESC
    LIMIT 5;
    """
    failure_questions = pd.read_sql(failure_query, con=engine)

    #modal data for the certified viewers
    query = """
            SELECT 
                v.id AS viewer_id,
                v.name AS viewer_name,
                m.module_name,
                COUNT(*) AS cleared_attempts
            FROM (
                SELECT 
                    viewer_id, 
                    module_id, 
                    attempt_no,
                    COUNT(question_id) AS total_questions,
                    COUNT(level_id) AS total_levels
                FROM viewer_answers
                GROUP BY viewer_id, module_id, attempt_no
            ) AS attempt_summary
            JOIN viewer v ON attempt_summary.viewer_id = v.id
            JOIN module m ON attempt_summary.module_id = m.id
            WHERE 
                (attempt_summary.module_id = 1 AND total_questions >= 10 AND total_levels >= 3)
                OR
                (attempt_summary.module_id = 2 AND total_questions >= 16 AND total_levels >= 6)
            GROUP BY v.id, v.name, m.module_name
            ORDER BY v.id, m.module_name;
        """
    df = pd.read_sql(query, con=engine)

    # Pivot the data to show module names as columns
    certified_viewers_details = df.pivot_table(
        index=['viewer_id', 'viewer_name'],
        columns='module_name',
        values='cleared_attempts',
        fill_value=0
    ).reset_index()


    failure_rate_query = """
    SELECT 
        m.module_name,
        CASE 
            WHEN COUNT(vs.id) = 0 THEN NULL
            ELSE ROUND(
                SUM(CASE WHEN vs.status = 'FAILED' THEN 1 ELSE 0 END) * 100 / 
                COUNT(vs.id), 
                4
            )
        END AS failure_rate
    FROM 
        module m
    LEFT JOIN 
        viewer_session vs 
        ON m.id = vs.last_module_id
    GROUP BY 
        m.module_name
    ORDER BY 
        failure_rate DESC;
    """
    failure_rate_by_module = pd.read_sql(failure_rate_query, con=engine)

    viewer_query = """
        SELECT v.id, 
            v.name, 
            v.email, 
            v.mobile, 
            d.name AS department_name, 
            v.is_active
        FROM viewer v
        LEFT JOIN department d ON v.department_id = d.id
        ORDER BY v.id;
    """
    viewer_details = pd.read_sql(viewer_query, con=engine)

    return {
        'total_viewers': total_viewers,
        'revenue': None,  # Placeholder
        'sessions': total_traings,  # Placeholder
        'certified_viewers': certified_viewers,  # Placeholder
        'churn_rate': None,  # Placeholder
        'failure': failure_percentage,
        'module_stats': module_stats,
        'viewer_table': viewer_table,
        'module_training_counts': module_training_counts,
        'failure_questions': failure_questions,

        #modal data
        'certified_viewers_details': certified_viewers_details,
        'failure_rate_by_module': failure_rate_by_module,
        'viewer_details': viewer_details,
    }


def home_layout():
    analytics_data = perform_analytics()
    module_table = analytics_data['module_stats']
    viewer_table = analytics_data['viewer_table']
    module_training_counts = analytics_data['module_training_counts']
    failure_questions = analytics_data['failure_questions']

    #modal data
    certified_viewers_details = analytics_data['certified_viewers_details']
    failure_rate_by_module = analytics_data['failure_rate_by_module']
    viewer_details = analytics_data['viewer_details']


    
    def display_value(value):
        return value if value is not None else "Loading..."

    #module wise trainigs
    bar_fig = go.Figure(data=[
        go.Bar(
            x=module_training_counts['module_name'],
            y=module_training_counts['total_training_sessions'],
            marker_color='rgba(58, 71, 80)',
            text=module_training_counts['total_training_sessions'],
            textposition='auto',
            hoverinfo='skip',
            textfont=dict(color='white')

        )
    ])

    bar_fig.update_layout(
        # title='Total Trainings per Module',
        # xaxis_title='Module Name',
        # yaxis_title='Training Sessions',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            tickfont=dict(color='white')  # X-axis text color
        ),
        yaxis=dict(
            tickfont=dict(color='white')  # Y-axis text color
        ),
    )


    # Failure questions bar chart
    failure_fig = go.Figure(go.Bar(
        x=failure_questions['failure_count'],
        y=failure_questions['question_abbr'],
        text=failure_questions['failure_count'],
        orientation='h',
        marker_color='#FF6F61',
        hoverinfo='skip',
        textfont=dict(color='white')
    ))

    failure_fig.update_layout(
        xaxis=dict(
            tickfont=dict(color='white')  # X-axis text color
        ),
        yaxis=dict(
            tickfont=dict(color='white')  # Y-axis text color
        ),
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )

    # ✅ Module Stats Table (Plotly)
    module_stats_table = go.Figure(data=[go.Table(
        header=dict(
            values=["Module Name", "Completions", "Failure Rate (%)", "Avg. Time"],
            fill_color='rgba(0,0,0,0)',
            align='center',
            font=dict(color='white', size=14),
            line_color='white',
            height=40
        ),
        cells=dict(
            values=[
                module_table['module_name'],
                module_table['total_training_sessions'],
                module_table['failed_percentage'],
                module_table['avg_time'],
            ],
            fill_color='rgba(0,0,0,0)',
            align='center',
            line_color='white',
            font=dict(color='white', size=14),
            height=40,
            
        )
    )])
    module_stats_table.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        height=300,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'   
    )

    # ✅ Viewer Table (Plotly)
    viewer_stats_table = go.Figure(data=[go.Table(
        header=dict(
            values=["Viewer ID", "Viewer Name", "Department", "Module Name", "Status", "Score"],
            fill_color='rgba(0,0,0,0)',
            align='center',
            font=dict(color='white', size=14),
            line_color='white'
        ),
        cells=dict(
            values=[
                viewer_table['viewer_id'],
                viewer_table['viewer_name'],
                viewer_table['department_name'],
                viewer_table['module_name'],
                viewer_table['status'],
                viewer_table['score'],
            ],
            fill_color='rgba(0,0,0,0)',
            align='center',
            line_color='white',
            font=dict(color='white', size=12),
            height=29
        )
    )])
    viewer_stats_table.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        height=300,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'   
    )


    return html.Div([
        html.Div([
            html.Div([
                html.H4("Total Viewers"),
                html.P(display_value(analytics_data['total_viewers']))
            ], className='dashboard-card', id='card-viewers', n_clicks=0, style={'cursor': 'pointer'}),

            html.Div([
                html.H4("Completed Trainings"),
                html.P(display_value(analytics_data['sessions']))
            ], className='dashboard-card'),

            html.Div([
                html.H4("Certified Viewers"),
                html.P(display_value(analytics_data['certified_viewers']))
            ], className='dashboard-card', id='card-certified', n_clicks=0, style={'cursor': 'pointer'}),

            html.Div([
                html.H4("Avg. Failure Rate"),
                html.P(display_value(analytics_data['failure']))
            ], className='dashboard-card', id='card-failure', n_clicks=0, style={'cursor': 'pointer'}),
        ], className='dashboard-row'),
        
        html.Div([
            html.Div([
                html.Div([
                    html.H4("Training Modules"),
                    dcc.Graph(figure=module_stats_table, config={'displayModeBar': False}, style={'height': '160px','border': '2px solid white','borderRadius': '12px',
                                'overflow': 'hidden',})
                ], className='left-inner-box'),

                html.Div([
                    html.H4("Trainees"),
                    dcc.Graph(figure=viewer_stats_table, config={'displayModeBar': False},  style={'height': '200px','border': '2px solid white','borderRadius': '12px',
                                'overflow': 'hidden',})
                ], className='left-inner-box'),
            ], className='dashboard-left'),

            html.Div([
                html.Div([
                    html.H4("Leadership Board"),
                    dcc.Graph(figure=bar_fig, config={'displayModeBar': False}, style={'height': '250px'})
                ], className='right-inner-box'),

                html.Div([
                    html.H4("Failure Steps Insights"),
                    dcc.Graph(figure=failure_fig, config={'displayModeBar': False}, style={'width': '100%','height': '250px'})
                ], className='right-inner-box'),

                # html.Div([
                #     html.H4("Certification"),
                #     html.P("Additional analytics or details.")
                # ], className='right-inner-box'),
            ], className='dashboard-right'),
            html.Div([
                html.Div([
                    html.H4("Certified Viewers Count By Modules"),
                            dcc.Graph(
                                figure=go.Figure(data=[go.Table(
                                    header=dict(
                                        values=list(certified_viewers_details.columns),
                                        fill_color='rgba(0,0,0,1)',
                                        align='center',
                                        font=dict(color='white', size=14),
                                        line_color='white',
                                        height=40
                                    ),
                                    cells=dict(
                                        values=[certified_viewers_details[col] for col in certified_viewers_details.columns],
                                        fill_color='rgba(0,0,0,0)',
                                        align='center',
                                        line_color='white',
                                        font=dict(color='white', size=12),
                                        height=30
                                    )
                                )],
                                layout=dict(
                                    margin=dict(l=10, r=10, t=10, b=0),
                                    autosize=True,
                                    paper_bgcolor='rgba(0,0,0,0)',  # Transparent outside background
                                    plot_bgcolor='rgba(0,0,0,0)'   # Transparent plot area
                                )),
                                config={'displayModeBar': False},
                                style={'width': '100%', 'height': '100%'}
                            ),
                    html.Button("Close", id='close-modal', n_clicks=0, className='modal-close-btn')
                ], className='modal-content')
            ], id='certified-modal', className='modal', style={'display': 'none'}),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Avg. Failure Rate Detail")),
                    dbc.ModalBody(
                        dcc.Graph(
                            figure=go.Figure(data=[go.Table(
                                header=dict(
                                    values=["Module Name", "Failure Rate (%)"],
                                    fill_color='rgba(0,0,0,1)',
                                    align='center',
                                    font=dict(color='white', size=14),
                                    line_color='white',
                                    height=40
                                ),
                                cells=dict(
                                    values=[
                                        failure_rate_by_module['module_name'],
                                        failure_rate_by_module['failure_rate'],
                                    ],
                                    fill_color='rgba(0,0,0,0)',
                                    align='center',
                                    line_color='white',
                                    font=dict(color='white', size=12),
                                    height=30
                                )
                            )],
                            layout=dict(
                                margin=dict(l=10, r=10, t=10, b=0),
                                # autosize=True,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)'
                            )),
                            config={'displayModeBar': False},
                            style={'width': '100%', 'height': '200px'}
                        )
                    ),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="close-modal-failure", className="ms-auto", n_clicks=0)
                    ),
                ],
                id="modal-failure",
                is_open=False,
            ),
            dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Total Viewers Details")),
                dbc.ModalBody(
                    dcc.Graph(
                        figure=go.Figure(data=[go.Table(
                            header=dict(
                                values=["ID", "Name", "Email", "Mobile", "Department"],
                                fill_color='rgba(0,0,0,1)',
                                align='center',
                                font=dict(color='white', size=14),
                                line_color='white',
                                height=40
                            ),
                            cells=dict(
                                values=[
                                    viewer_details['id'],
                                    viewer_details['name'],
                                    viewer_details['email'],
                                    viewer_details['mobile'],
                                    viewer_details['department_name'],
                                ],
                                fill_color='rgba(0,0,0,0)',
                                align='center',
                                line_color='white',
                                font=dict(color='white', size=12),
                                height=30
                            )
                        )],
                        layout=dict(
                            margin=dict(l=10, r=10, t=10, b=0),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)'
                        )),
                        config={'displayModeBar': False},
                        style={'width': '100%', 'height': '300px'}
                    )
                ),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close-modal-viewers", className="ms-auto", n_clicks=0)
                ),
            ],
            id="modal-viewers",
            is_open=False,
        )

        ], className='dashboard-bottom'),

    ], id="dashboard-container")
