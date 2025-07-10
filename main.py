from flask import Flask, render_template, request, redirect, session
import dash
from dash import html, dcc, Input, Output, State

from dashboard.dashboard_layout import create_dashboard_layout
from dashboard.home import home_layout
from dashboard.reports import reports_layout
from dashboard.trainee import trainee_layout
from dashboard.module import module_layout
from dashboard.certification import certificate_layout
from dashboard.setting import setting_layout

# Flask Setup
server = Flask(__name__)
server.secret_key = 'your_secret_key_here'

@server.route('/')
def index():
    return redirect('/login')

@server.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'praveen' and password == 'password123':
            session['logged_in'] = True
            session['username'] = username 
            return redirect('/dashboard/')
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@server.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@server.before_request
def restrict_dashboard():
    if request.path.startswith('/dashboard') and not session.get('logged_in'):
        return redirect('/login')

# Dash App Integration
app = dash.Dash(__name__, server=server, url_base_pathname='/dashboard/', external_stylesheets=['/static/style.css'], suppress_callback_exceptions=True )
app.layout = create_dashboard_layout

# Page Routing Callback
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname in ('/dashboard/', '/dashboard/home'):
        return home_layout()
    elif pathname == '/dashboard/reports':
        return reports_layout()
    elif pathname == '/dashboard/trainee-management':
        return trainee_layout()
    elif pathname == '/dashboard/module-management':
        return module_layout()
    elif pathname == '/dashboard/certification':
        return certificate_layout()
    elif pathname == '/dashboard/settings':
        return setting_layout()
    elif pathname == '/logout':
        return dcc.Location(pathname='/login', id='redirect')
    else:
        return html.H2("404 - Page Not Found")

# ✅ Updated callback to auto-update charts on dropdown change (no button needed)
@app.callback(
    [
        Output('bar-chart', 'figure'),
        Output('pie-chart', 'figure'),
    ],
    [
        Input('date-dropdown', 'value'),
        Input('dept-dropdown', 'value'),
        Input('module-dropdown', 'value'),
        Input('status-dropdown', 'value'),
    ]
)
def update_charts(date, department, module, status):
    from dashboard.reports import get_data
    try:
        # Call get_data with whatever filters are selected
        data = get_data(department=department, module=module, status=status, date=date)
        return data['training_by_month_fig'], data['pie_chart']
    except Exception as e:
        # In case of error, log it and return empty figures
        print(f"Error in update_charts: {e}")
        return {}, {}
    
@app.callback(
    Output("modal-certified", "is_open"),
    [Input("card-certified", "n_clicks"), Input("close-modal-certified", "n_clicks")],
    [State("modal-certified", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-failure", "is_open"),
    [Input("card-failure", "n_clicks"), Input("close-modal-failure", "n_clicks")],
    [State("modal-failure", "is_open")]
)
def toggle_modal(card_click, close_click, is_open):
    if card_click or close_click:
        return not is_open
    return is_open

@app.callback(
    Output("modal-viewers", "is_open"),
    [Input("card-viewers", "n_clicks"), Input("close-modal-viewers", "n_clicks")],
    [State("modal-viewers", "is_open")],
)
def toggle_modal_viewers(open_click, close_click, is_open):
    if open_click or close_click:
        return not is_open
    return is_open

@app.callback(
    Output("modal-trainings", "is_open"),
    [Input("card-trainings", "n_clicks"), Input("close-modal-trainings", "n_clicks")],
    [State("modal-trainings", "is_open")],
)
def toggle_modal_trainings(open_click, close_click, is_open):
    if open_click or close_click:
        return not is_open
    return is_open

@app.callback(
    Output('failure-steps-chart', 'figure'),
    Input('module-dropdown-filter', 'value'),
)
def update_failure_chart(module_id):
    from dashboard.home import perform_analytics
    import plotly.graph_objs as go

    analytics_data = perform_analytics(module_id=module_id)
    failure_questions = analytics_data['failure_questions']

    if failure_questions.empty:
        # No Data Case: Show Text Only
        failure_fig = go.Figure()
        failure_fig.add_annotation(
            text="No Data Available",
            xref="paper", yref="paper",
            x=0.2, y=0.5, showarrow=False,
            font=dict(size=20, color="white"),
            align="center"
        )
        failure_fig.update_layout(
            xaxis={'visible': False},
            yaxis={'visible': False},
            height=250,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=0, b=0)
        )
    else:
        # Normal Case: Draw Bar Chart
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
            xaxis=dict(tickfont=dict(color='white')),
            yaxis=dict(tickfont=dict(color='white')),
            margin=dict(l=20, r=20, t=40, b=20),
            height=250,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )

    return failure_fig


if __name__ == '__main__':
    server.run(debug=True)
