from dash import html, dcc
import plotly.express as px
import pandas as pd

def trainee_layout():
    return html.Div([  
        html.H1(["Trainee Management"],style={'color':'white','marginTop':'20%'}),
        html.H4(['under development'],style={'color':'white'})
    ], style={'textAlign':'center'})
