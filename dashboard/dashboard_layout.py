from dash import html, dcc
from flask import session, has_request_context

def create_dashboard_layout():

    if has_request_context():
        username = session.get('username', 'User')
    else:
        username = 'User' 

    return html.Div([
        dcc.Location(id='url', refresh=False),

        html.Nav([
            html.Img(src='/static/logo.png', style={'height': '50px', 'margin-right': '20px'}),

            dcc.Link("Dashboard", href="/dashboard/home", className='nav-link', id='link-home'),
            dcc.Link("Trainee Management", href="/dashboard/trainee-management", className='nav-link', id='link-trainee'),
            dcc.Link("Module Management", href="/dashboard/module-management", className='nav-link', id='link-module'),
            dcc.Link("Certification", href="/dashboard/certification", className='nav-link', id='link-cert'),
            dcc.Link("Reports", href="/dashboard/reports", className='nav-link', id='link-reports'),
            dcc.Link("Settings", href="/dashboard/settings", className='nav-link', id='link-settings'),
            dcc.Link("Logout", href="/logout", className='nav-link', id='link-logout'),
            html.Div([
                html.Div([
                    html.Span("Welcome", style={'display': 'block','color':'white','fontSize':'12px'}),
                    html.Span(username, style={'display': 'block', 'font-weight': 'bold', 'color':'rgba(25, 201, 245, 1)'}),
                ]),
                html.Img(src='/static/user.png', style={'width': '50px', 'border-radius': '50%', 'margin-right': '8px'}),
            ], style={'margin-left': 'auto', 'display': 'flex', 'align-items': 'center','gap':'10px'})

        ], style={
            'padding': '20px',
            'background': '#273F4F',
            'display': 'flex',
            'align-items': 'center',
            'gap': '20px',
            'position':'fixed',
            'width':'100%',
            'zIndex':'1',
        }),

        html.Hr(),

        html.Div(id='page-content')
    ])
