import pandas as pd
import os
import subprocess
import textwrap

def generate_sped_funding_gap_html(input_excel, output_html, development_mode=False):
    xls = pd.ExcelFile(input_excel)
    sheet1_df = xls.parse('Sheet1')
    sheet2_df = xls.parse('Sheet2')

    columns_to_keep = [
        "DISTRICT NUMBER",
        "DISTRICT NAME",
        "Enrollment",
        "GF Students with Disabilities (PICs 23,33,43)",
        "23-Special Education Adjusted Allotment 48.102",
        "2022-2023 Special Education Funding Gap"
    ]
    column_rename = {
        "DISTRICT NUMBER": "District Number",
        "DISTRICT NAME": "District Name",
        "Enrollment": "Enrollment",
        "GF Students with Disabilities (PICs 23,33,43)": "SPED District Expenditure (GF)",
        "23-Special Education Adjusted Allotment 48.102": "SPED State Funding",
        "2022-2023 Special Education Funding Gap": "SPED Funding Gap"
    }

    sheet1_sorted = sheet1_df.sort_values(by="2022-2023 Special Education Funding Gap", ascending=False)
    sheet2_sorted = sheet2_df.sort_values(by="2022-2023 Special Education Funding Gap", ascending=False)

    districts_sorted = sheet1_sorted[columns_to_keep].rename(columns=column_rename)
    charters_sorted = sheet2_sorted[columns_to_keep].rename(columns=column_rename)

    districts_sorted["SPED Funding Gap Raw"] = districts_sorted["SPED Funding Gap"].replace(r'[\$,]', '', regex=True).astype(float)
    charters_sorted["SPED Funding Gap Raw"] = charters_sorted["SPED Funding Gap"].replace(r'[\$,]', '', regex=True).astype(float)

    def disambiguate_names(df):
        df["District Number"] = df["District Number"].apply(lambda x: f"'{int(x):06d}")
        duplicates = df["District Name"].duplicated(keep=False)
        df.loc[duplicates, "District Name"] = df.loc[duplicates].apply(
            lambda row: f"{row['District Name']} - {row['District Number']}", axis=1
        )
        return df

    districts_sorted = disambiguate_names(districts_sorted)
    charters_sorted = disambiguate_names(charters_sorted)

    # Add numeric columns for charting (Spent and Received)
    districts_sorted["Spent"] = districts_sorted["SPED District Expenditure (GF)"].apply(
        lambda x: float(x.replace("$", "").replace(",", "")) if isinstance(x, str) else float(x)
    )
    districts_sorted["Received"] = districts_sorted["SPED State Funding"].apply(
        lambda x: float(x.replace("$", "").replace(",", "")) if isinstance(x, str) else float(x)
    )
    charters_sorted["Spent"] = charters_sorted["SPED District Expenditure (GF)"].apply(
        lambda x: float(x.replace("$", "").replace(",", "")) if isinstance(x, str) else float(x)
    )
    charters_sorted["Received"] = charters_sorted["SPED State Funding"].apply(
        lambda x: float(x.replace("$", "").replace(",", "")) if isinstance(x, str) else float(x)
    )

    districts_surplus_count = (districts_sorted["SPED Funding Gap Raw"] > 0).sum()
    districts_deficit_count = (districts_sorted["SPED Funding Gap Raw"] < 0).sum()
    charters_surplus_count = (charters_sorted["SPED Funding Gap Raw"] > 0).sum()
    charters_deficit_count = (charters_sorted["SPED Funding Gap Raw"] < 0).sum()

    districts_surplus_total = districts_sorted.loc[districts_sorted["SPED Funding Gap Raw"] > 0, "SPED Funding Gap Raw"].sum()
    districts_deficit_total = districts_sorted.loc[districts_sorted["SPED Funding Gap Raw"] < 0, "SPED Funding Gap Raw"].sum()
    charters_surplus_total = charters_sorted.loc[charters_sorted["SPED Funding Gap Raw"] > 0, "SPED Funding Gap Raw"].sum()
    charters_deficit_total = charters_sorted.loc[charters_sorted["SPED Funding Gap Raw"] < 0, "SPED Funding Gap Raw"].sum()

    districts_net_gap = districts_surplus_total + districts_deficit_total
    charters_net_gap = charters_surplus_total + charters_deficit_total
    total_net_gap = districts_net_gap + charters_net_gap

    districts_surplus_pct = (districts_surplus_count / (districts_surplus_count + districts_deficit_count) * 100) if (districts_surplus_count + districts_deficit_count) > 0 else 0
    districts_deficit_pct = (districts_deficit_count / (districts_surplus_count + districts_deficit_count) * 100) if (districts_surplus_count + districts_deficit_count) > 0 else 0
    charters_surplus_pct = (charters_surplus_count / (charters_surplus_count + charters_deficit_count) * 100) if (charters_surplus_count + charters_deficit_count) > 0 else 0
    charters_deficit_pct = (charters_deficit_count / (charters_surplus_count + charters_deficit_count) * 100) if (charters_surplus_count + charters_deficit_count) > 0 else 0

    def format_currency(val):
        val = int(val)
        return f"-${abs(val):,}" if val < 0 else f"${val:,}"

    def format_enrollment(val):
        return f"{int(val):,}"

    for df in [districts_sorted, charters_sorted]:
        df["Enrollment"] = df["Enrollment"].apply(format_enrollment)
        for col in ["SPED District Expenditure (GF)", "SPED State Funding", "SPED Funding Gap"]:
            df[col] = df[col].apply(format_currency)

    districts_json = districts_sorted.to_dict(orient="records")
    charters_json = charters_sorted.to_dict(orient="records")

    html_template = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>SPED Funding Gap (2022-2023)</title>
        <link rel="icon" type="image/png" href="favicon-96x96.png" sizes="96x96" />
        <link rel="icon" type="image/svg+xml" href="favicon.svg" />
        <link rel="shortcut icon" href="favicon.ico" />
        <link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png" />
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css"/>
        <style>
            body {{ font-family: Helvetica, sans-serif; margin: 40px auto; padding-left: 40px; padding-right: 40px; max-width: 900px; opacity: 0; transition: opacity 0.4s ease-in; }}
            body.loaded {{
                opacity: 1;
            }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f4f4f4; }}
            .dataTables_wrapper .dataTables_length,
            .dataTables_wrapper .dataTables_filter {{
                margin-bottom: 15px;
            }}
            .hidden {{
                display: none;
            }}
            .table-container {{
                overflow-x: auto;
                width: 100%;
            }}

            .logo-container {{
                padding: 4px;
                display: flex;
                justify-content: flex-end;
                align-items: center;
            }}

            .logo-container a, .logo-container span {{
                display: flex;
                align-items: center;
                text-decoration: none;
            }}

            .logo-container img {{
                display: block;
                height: 16px;
            }}

            .logo-container a:last-child {{
                font-size: 14px;
            }}

            @media screen and (max-width: 600px) {{
                table, th, td {{
                    font-size: 12px;
                    padding: 4px;
                }}
                /* Duplicate logo-container styles removed */
            }}
            
            .summary-stats li {{
                opacity: 0;
                transform: translateY(20px);
                animation: slideUp 0.5s ease forwards;
                animation-play-state: paused;
            }}
            .summary-stats li:nth-child(1) {{ animation-delay: 0.1s; }}
            .summary-stats li:nth-child(2) {{ animation-delay: 0.2s; }}
            .summary-stats li:nth-child(3) {{ animation-delay: 0.3s; }}
            
            @keyframes slideUp {{
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            // Note: changes to the plugin code is not reflected to the chart, because the plugin is loaded at chart construction time and editor changes only trigger an chart.update().
            const plugin = {{
              id: 'customCanvasBackgroundColor',
              beforeDraw: (chart, args, options) => {{
                const {{ctx}} = chart;
                ctx.save();
                ctx.globalCompositeOperation = 'destination-over';
                ctx.fillStyle = options.color || 'white';
                ctx.fillRect(0, 0, chart.width, chart.height);
                ctx.restore();
              }}
            }};
        </script>
    </head>
    <body>

    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h1 style="margin: 0;">2022-2023 Special Education Funding Gap</h1>
        <div class="logo-container" style="padding: 4px; display: flex; justify-content: flex-end; align-items: center;">
            <a href="https://x.com/TxEdInfo" target="_blank" style="text-decoration: none; margin-right: 8px;">
                <img src="logo-black.png" alt="X.com" width="16" height="16">
            </a>
            <a href="https://github.com/txedinfo/SPEDFundingGap" target="_blank" style="text-decoration: none;">
                <img src="GitHub_Logo.png" alt="github.com" height="16">
            </a>
            <span id="contact-link"></span>
            <script>
              (function() {{
                const user = "txpubliceducationinfo";
                const domain = "gmail.com";
                const email = user + "@" + domain;
                const link = `<a href="mailto:${{email}}" style="margin-left: 8px; font-size: 14px; text-decoration: none;">Contact</a>`;
                document.getElementById("contact-link").innerHTML = link;
              }})();
            </script>
        </div>
    </div>

    <p>
        The following analysis reflects the special education (SPED) funding gap for Texas public school districts and charter schools for the 2022-2023 school year using the latest final data publicly available from the Texas Education Agency (see below for citations). The final data for the 2023-2024 school year will be available in Spring 2025 and this analysis will be updated at that time.
    </p>
    <p>
        The SPED funding gap reflects the difference between what districts spend on SPED (GF Students with Disabilities-PICs 23,33,43) and the funding they receive from the state (23-Special Education Adjusted Allotment 48.102).
    </p>
    <p>
        The full dataset can be downloaded here: <a href="https://docs.google.com/spreadsheets/d/1VFcxNdg7vcTgO1QTFSPHkAsh0L09omZJ/edit?usp=sharing&amp;ouid=110674123000325431228&amp;rtpof=true&amp;sd=true" target="_blank">Google Sheets</a>
    </p>

    <h3 style="margin-top: 30px;">Summary Statistics</h3>
    <ul class="summary-stats">
        <li><strong>Districts</strong>
          <ul>
            <li>With surplus: {districts_surplus_count} ({districts_surplus_pct:.1f}%)</li>
            <li>With deficit: {districts_deficit_count} ({districts_deficit_pct:.1f}%)</li>
            <li>Net Funding Gap: {"-$" + format(abs(int(districts_net_gap)), ',') if districts_net_gap < 0 else "$" + format(int(districts_net_gap), ',')}</li>
          </ul>
        </li>
        <br/>
        <li><strong>Charters</strong>
          <ul>
            <li>With surplus: {charters_surplus_count} ({charters_surplus_pct:.1f}%)</li>
            <li>With deficit: {charters_deficit_count} ({charters_deficit_pct:.1f}%)</li>
            <li>Net Funding Gap: {"-$" + format(abs(int(charters_net_gap)), ',') if charters_net_gap < 0 else "$" + format(int(charters_net_gap), ',')}</li>
          </ul>
        </li>
        <br/>
        <li><strong>Total Net Funding Gap:</strong> <span style="background-color:#f8d7da;">{"-$" + format(abs(int(total_net_gap)), ',') if total_net_gap < 0 else "$" + format(int(total_net_gap), ',')}</span></li>
    </ul>

    <div style="border: 1px solid lightgrey; border-radius: 4px; padding: 15px; margin-top: 30px;">    
        <!-- The chart title is now set via Chart.js, so no h2 here -->
        <!-- Chart container for Districts -->
        <div id="districts-chart-container" style="margin-bottom: 20px;"></div>
        <div class="table-container">
            <div id="districts-table-container"></div>
        </div>
    </div>

    <div style="border: 1px solid lightgrey; border-radius: 4px; padding: 15px; margin-top: 30px;">    
        <!-- The chart title is now set via Chart.js, so no h2 here -->
        <!-- Chart container for Charters -->
        <div id="charters-chart-container" style="margin-bottom: 20px;"></div>
        <div class="table-container">
            <div id="charters-table-container"></div>
        </div>
    </div>

    <h3 style="margin-top: 30px;">Sources of data:</h3>
    <p>
        <ul>
            <li>District expenditures: <a href="https://rptsvr1.tea.texas.gov/school.finance/forecasting/financial_reports/2223_FinActRep.html" target="_blank">2022-2023 PEIMS Financial Standard Reports,</a> GF Students with Disabilities (PICs 23,33,43)</li>
            <li>State funding: <a href="https://tealprod.tea.state.tx.us/fsp/Reports/ReportSelection.aspx" target="_blank">2022-2033 Summary of Finances,</a> 23-Special Education Adjusted Allotment 48.102</li>
        </ul>
    </p>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <script>
        function renderDataTable(data, containerId) {{
            const tableId = containerId + '-table';
            // Build columns definition based on data keys
            let columns = [];
            for (let key in data[0]) {{
                if (key === "Spent" || key === "Received") {{
                    columns.push({{ title: key, data: key, visible: false }});
                }} else if (key !== "District Number" && key !== "SPED Funding Gap Raw") {{
                    columns.push({{ title: key, data: key }});
                }}
            }}
            let html = `<table id="${{tableId}}" class="display"></table>`;
            document.getElementById(containerId).innerHTML = html;
            let dt = new DataTable(`#${{tableId}}`, {{
                data: data,
                columns: columns,
                pageLength: 10,
                autoWidth: false,
                order: [[4, 'asc']]
            }});

            // Setup chart container: the chart will be placed above the table controls
            const chartContainerId = containerId.replace("table-container", "chart-container");
            let chartContainer = document.getElementById(chartContainerId);
            if (!chartContainer) {{
                chartContainer = document.createElement("div");
                chartContainer.id = chartContainerId;
                chartContainer.style.marginBottom = "20px";
                document.getElementById(containerId).parentNode.insertBefore(chartContainer, document.getElementById(containerId));
            }}

            // Create a canvas for the chart and a download button
            chartContainer.innerHTML = '<canvas id="' + tableId + '-chart" style="height:400px; max-height:400px;"></canvas><br><button id="' + tableId + '-download">Download Chart</button>';            const ctx = document.getElementById(tableId + '-chart').getContext('2d');

            function updateChart() {{
                let currentData = dt.rows({{ page: 'current' }}).data().toArray();
                let labels = currentData.map(row => row["District Name"]);
                let spentData = currentData.map(row => parseFloat(row["Spent"]));
                let receivedData = currentData.map(row => parseFloat(row["Received"]));

                console.log("Chart Data:", labels, spentData, receivedData);

                // Destroy previous chart for this table if exists
                window.chartInstances = window.chartInstances || {{}};
                if (window.chartInstances[tableId]) {{
                    window.chartInstances[tableId].destroy();
                }}
                window.chartInstances[tableId] = new Chart(ctx, {{
                    type: 'bar',
                    plugins: [plugin],
                    data: {{
                        labels: labels,
                        datasets: [
                            {{
                                label: 'Spent',
                                data: spentData,
                                backgroundColor: 'darkred'
                            }},
                            {{
                                label: 'Received',
                                data: receivedData,
                                backgroundColor: 'lightcoral'
                            }}
                        ]
                    }},
                    options: {{
                        maintainAspectRatio: true,
                        animation: {{
                            duration: 1000,
                            easing: 'easeOutQuart'
                        }},
                        scales: {{
                            y: {{
                                ticks: {{
                                    callback: function(value, index, values) {{
                                        return '$' + value.toLocaleString();
                                    }}
                                }}
                            }}
                        }},
                        plugins: {{
                            customCanvasBackgroundColor: {{
                                color: 'white',
                            }},
                            title: {{
                                display: true,
                                text: tableId.indexOf("districts") !== -1 ? "Districts by 2022-2023 SPED Funding Gap" : "Charters by 2022-2023 SPED Funding Gap",
                                color: 'black',
                                font: {{
                                    size: 20
                                }}
                            }},
                            legend: {{
                                display: true,
                                labels: {{
                                    boxWidth: 12
                                }}
                            }},
                        }},
                    }}
                }});
            }}

            updateChart();
            dt.on('draw', function() {{
                updateChart();
            }});

            document.getElementById(tableId + '-download').addEventListener('click', function() {{
                let link = document.createElement('a');
                link.href = window.chartInstances[tableId].toBase64Image();
                link.download = tableId.replace('-table-container-table', '_22.23 SPED funding gap') + ' chart.png';
                link.click();
            }});
        }}

        renderDataTable({districts_json}, 'districts-table-container');
        renderDataTable({charters_json}, 'charters-table-container');
    </script>
    <script>
      window.addEventListener("load", () => {{
        document.body.classList.add("loaded");
      }});
        document.querySelectorAll(".summary-stats li").forEach(el => {{
            el.style.animationPlayState = 'running';
        }});
    </script>
    </body>
    </html>
    """)

    if development_mode:
        output_dir = os.path.dirname(os.path.abspath(output_html))
        os.chdir(output_dir)
        print("Starting development server at http://localhost:8000...")
        subprocess.run(["python3", "-m", "http.server", "8000"])

    with open(output_html, "w") as f:
        f.write(html_template)


if __name__ == "__main__":
    generate_sped_funding_gap_html(
        "/Users/adpena/PycharmProjects/OSOD/OSOD 2024 Report_2022-2023 SPED Funding Gap.xlsx",
        "index.html",
        development_mode=True
    )
