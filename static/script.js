// Default values
const defaultValues = {
    loan_amnt: 10000,
    term: "36 months",
    int_rate: 12.5,
    installment: 300,
    grade: "B",
    sub_grade: "B2",
    emp_length: "5 years",
    home_ownership: "RENT",
    annual_inc: 50000,
    verification_status: "Verified",
    issue_d: "Jan-2020",
    purpose: "debt_consolidation",
    dti: 15.0,
    open_acc: 10,
    pub_rec: 0,
    revol_bal: 2000,
    revol_util: 30.0,
    total_acc: 20,
    initial_list_status: "w",
    application_type: "INDIVIDUAL",
    mort_acc: 0,
    pub_rec_bankruptcies: 0
};

// Dropdown options from trained data
const categoricalOptions = {
    term: ["36 months", "60 months"],
    grade: ["A","B","C","D","E","F","G"],
    sub_grade: ["A1","A2","A3","A4","A5","B1","B2","B3","B4","B5","C1","C2","C3","C4","C5","D1","D2","D3","D4","D5","E1","E2","E3","E4","E5","F1","F2","F3","F4","F5","G1","G2","G3","G4","G5"],
    emp_length: ["< 1 year","1 year","2 years","3 years","4 years","5 years","6 years","7 years","8 years","9 years","10+ years"],
    home_ownership: ["MORTGAGE","RENT","OWN","OTHER","NONE","ANY"],
    verification_status: ["Verified","Source Verified","Not Verified"],
    purpose: ["debt_consolidation","credit_card","home_improvement","other","major_purchase","small_business","car","medical","moving","vacation","house","wedding","renewable_energy","educational"],
    initial_list_status: ["f","w"],
    application_type: ["INDIVIDUAL","JOINT","DIRECT_PAY"]
};

let numBorrowers = 1;

function generateInputs() {
    let form = document.getElementById("borrowersForm");
    form.innerHTML = "";
    numBorrowers = parseInt(document.getElementById("numBorrowersInput").value);

    for (let i = 0; i < numBorrowers; i++) {
        let div = document.createElement("div");
        div.className = "borrower";
        div.id = `borrower${i+1}`;
        div.innerHTML = `<h3>Borrower ${i+1}</h3>` +
        `Loan ID: <input type="text" name="loan_id" value=""><br>` + 
            Object.keys(defaultValues).map(key => {
                if (categoricalOptions.hasOwnProperty(key)) {
                    return `${key.replace(/_/g," ")}: <select name="${key}">` +
                        categoricalOptions[key].map(opt => 
                            `<option value="${opt}" ${opt === defaultValues[key] ? "selected" : ""}>${opt}</option>`
                        ).join("") +
                        `</select><br>`;
                } else {
                    let value = defaultValues[key];
                    let step = Number.isInteger(value) ? "" : " step='0.01'";
                    let type = typeof value === "number" ? "number" : "text";
                    return `${key.replace(/_/g, " ")}: <input type="${type}" name="${key}" value="${value}"${step}><br>`;
                }
            }).join("");
        form.appendChild(div);
    }
}

async function submitData() {
    let resultsDiv = document.getElementById("results");
    resultsDiv.innerHTML = "";

    let borrowers = [];
    let hasError = false;

    for (let i = 1; i <= numBorrowers; i++) {
        let borrower = {};
        let borrowerDiv = document.getElementById(`borrower${i}`);
        let inputs = borrowerDiv.querySelectorAll("input, select");

        inputs.forEach(input => {
            let value = input.value.trim();
            if (value === "") {
                input.style.border = "2px solid red";
                hasError = true;
            } else {
                input.style.border = "";
            }

            if (input.type === "number") borrower[input.name] = parseFloat(value);
            else borrower[input.name] = value;
        });

        borrowers.push(borrower);
    }

    if (hasError) {
        resultsDiv.innerHTML = `<p style="color:red;">Please fill in all required fields highlighted in red.</p>`;
        return;
    }

    try {
        let response = await fetch("/predict", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-User-Email": localStorage.getItem("activeUser") || "guest"
            },
            body: JSON.stringify(borrowers)
        });
          

        let data = await response.json();

        if (data.error) {
            resultsDiv.innerHTML = `<p style="color:red;">${data.error}</p>`;
        } else {
            displayResults(data);
        }
    } catch (error) {
        resultsDiv.innerHTML = `<p style="color:red;">Failed to fetch. Please try again.</p>`;
        console.error("Error:", error);
    }
}

function displayResults(data) {
    const resultsDiv = document.getElementById("results");
    resultsDiv.innerHTML = "<h2>Prediction Results</h2>";
  
    data.forEach((res, idx) => {
      // Determine CSS class based on risk
      let riskClass = "";
      if (res.risk_level.toLowerCase().includes("low")) riskClass = "low";
      else if (res.risk_level.toLowerCase().includes("medium")) riskClass = "medium";
      else riskClass = "high";
  
      resultsDiv.innerHTML += `
        <div class="result-card ${riskClass}">
          <h3>Borrower ${idx + 1}</h3>
          <p><strong>Default Probability:</strong> ${res.default_probability}</p>
          <p><strong>Risk Level:</strong> ${res.risk_level}</p>
          <p><strong>Recommended Action:</strong> ${res.recommended_action}</p>
        </div>
      `;
    });
  }
  


// --- Logs Fetching ---
async function loadLogs() {
    const res = await fetch("/logs", {
      headers: {
        "X-User-Email": localStorage.getItem("activeUser") || "guest"
      }
    });
    const logs = await res.json();
    const tbody = document.querySelector("#logTable tbody");
    tbody.innerHTML = logs.map(l =>
      `<tr>
        <td>${l.borrower?.loan_id || "-"}</td>
        <td>${l.default_probability}</td>
        <td>${l.risk_level}</td>
        <td>${l.recommended_action}</td>
        <td>${l.timestamp}</td>
      </tr>`
    ).join('');
  }
  

console.log("script loaded successfully");
