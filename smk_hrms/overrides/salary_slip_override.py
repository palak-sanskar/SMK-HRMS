import frappe
from frappe import _
from hrms.hr.doctype.leave_application.leave_application import validate_active_employee
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip as TransactionBase, sanitize_expression
import re
from frappe.utils import formatdate, getdate

class SalarySlip(TransactionBase):
    def validate(self):
        self.check_salary_withholding()
        self.status = self.get_status()
        validate_active_employee(self.employee)
        self.validate_dates()
        self.check_existing()
        
        if not self.salary_slip_based_on_timesheet:
            self.get_date_details()
        
        
        if not (len(self.get("earnings")) or len(self.get("deductions"))):
			
            self.get_emp_and_working_day_details()
        else:
            self.get_working_days_details(lwp=self.leave_without_pay)

        self.set_salary_structure_assignment()
        if self.is_new():
            self.calculate_net_pay()
        self.compute_year_to_date()
        self.compute_month_to_date()
        self.compute_component_wise_year_to_date()

        self.add_leave_balances()
        if not self.is_new():
            self.calculate_employer_contribution()

        max_working_hours = frappe.db.get_single_value(
            "Payroll Settings", "max_working_hours_against_timesheet"
        )
        if max_working_hours:
            if self.salary_slip_based_on_timesheet and (self.total_working_hours > int(max_working_hours)):
                frappe.msgprint(
                    _("Total working hours should not be greater than max working hours {0}").format(
                        max_working_hours
                    ),
                    alert=True,
                )

    def calculate_employer_contribution(self):      
        emp = self.employee
        salary_structure = self.salary_structure
        start_date = self.start_date 
        formatted_date = formatdate(start_date, "dd-mm-yyyy")  # Format to dd-mm-yyyy
        start_month = getdate(start_date).month  # Extract the month from the start_date
        # frappe.msgprint(_("Formatted Start Date: {0}, Month: {1}").format(formatted_date, start_month))
        if not self.custom_employer_contribution_table:
            if not salary_structure:
                frappe.throw(_("Salary Structure is not set in the Salary Slip"))

            # Fetch Salary Structure and Assignment
            salary_structure_doc = frappe.get_doc("Salary Structure", salary_structure)
            salary_structure_assignment = frappe.get_all(
                "Salary Structure Assignment",
                filters={"employee": emp, "salary_structure": salary_structure},
                fields=["base"]
            )
            
            if not salary_structure_assignment:
                frappe.throw(_("No Salary Structure Assignment found for this employee and salary structure."))
            
            base = salary_structure_assignment[0].base
            # abbr = "B_1" # The abbreviation you want to look for
            
            component_name, component_value, found_abbr = find_salary_component(self)

            # If component is None or 0, skip processing this component
            if component_name is None or component_value == 0:            
                component_value = 0 

            # frappe.msgprint(_("Found Salary Component: {0}, Amount: {1}").format(component_name, component_value))

            # Prepare variables for formula evaluation
            variables = {found_abbr: component_value, "base": base, "start_month": start_month}
        
            self.custom_employer_contribution_table = []
        
            # Iterate through custom employer contribution table and evaluate formulas
            for row in salary_structure_doc.custom_employer_contribution_table:
                evaluated_formula = 0
                if row.formula:
                    # Replace "getdate(start_date).month" dynamically with `start_month`
                    formula = row.formula.replace("getdate(start_date).month", str(start_month))
                    
                    evaluated_formula, error = evaluate_formula_parts(formula, variables, self)
                    if error:
                        evaluated_formula = 0 
                        continue
                    
                    if row.salary_component in [
                        "Labor Welfare Fund SMK",
                        "Labor Welfare Fund Employer Share"
                    ]:
                        comp_type = frappe.get_value(
                            "Salary Component",
                            row.salary_component,
                            "custom_salary_component_type"
                        )

                        if not (
                            comp_type in ["LWF Employer", "LWF"]
                            and frappe.get_value("Employee", self.employee, "custom_lwf_consent") == 1
                        ):
                            evaluated_formula = 0

                self.append("custom_employer_contribution_table", {
                    "salary_component": row.salary_component,
                    "amount": evaluated_formula
                })
            

            # Notify the user
            # frappe.msgprint(_("Employee: {0}<br>Salary Structure: {1}<br>Base: {2}<br>Salary Components and Formulas have been added.").format(
            #     emp, salary_structure, base), title=_("Details")
            # )

import frappe, re
from frappe.utils import getdate, date_diff

def evaluate_formula_parts(formula, variables, self):
    """Evaluate salary formula safely with support for date_diff(), employee fields, variables, and ternary conditions."""

    # Fetch Employee document (with all custom fields)
    emp_doc = frappe.get_doc("Employee", self.employee)
    emp_doj = emp_doc.date_of_joining

    try:
        # Check if the formula is a direct number (e.g., "1800" or "2000")
        if formula.isdigit():
            return float(formula), None

        # ---- 1 Replace Employee field references dynamically ----
        original_formula = formula 
        emp_fields = frappe.get_meta("Employee").fields
        for f in emp_fields:
            if f.fieldname in formula:
                val = emp_doc.get(f.fieldname)
                val_str = str(val).replace(",", "").replace("₹", "").strip()
                try:
                    float(val_str)
                except:
                    pass
                    # val_str = "0"
                formula = re.sub(rf"\b{f.fieldname}\b", val_str, formula)

        # ---- 2 Handle date_diff(...) expressions ----
        if "date_diff(" in formula:
            pattern = r"date_diff\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*\)"
            
            matches = re.findall(pattern, original_formula)
            
            for end_expr, start_expr in matches:
                end_expr, start_expr = end_expr.strip(), start_expr.strip()
                
                # Resolve variables to actual values
                if end_expr == "end_date":
                    end_value = self.end_date
                elif hasattr(self, end_expr):
                    end_value = getattr(self, end_expr)
                else:
                    end_value = emp_doc.get(end_expr)

                # start_value = emp_doj
                if start_expr == "date_of_joining":
                    start_value = emp_doj
                elif hasattr(self, start_expr):
                    start_value = getattr(self, start_expr)
                else:
                    start_value = emp_doc.get(start_expr)
                    
                # Compute difference
                if end_value and start_value:
                    diff = date_diff(getdate(end_value), getdate(start_value))
    
                else:
                    diff = 0

                # Replace in formula
               
                formula = original_formula.replace(f"date_diff({end_expr}, {start_expr})", str(diff))
                
                
        # ---- 3 Handle ternary expressions (x if y else z) ----
        match = re.match(r'\((.*?)\)\s*if\s*(.*?)\s*else\s*(.*)', formula)
        if match:
            true_expr, condition_expr, false_expr = match.groups()

            # Substitute variables in condition
            for var, val in variables.items():
                if isinstance(val, tuple):
                    val = val[0]
                condition_expr = re.sub(rf"\b{var}\b", str(val or 0), condition_expr)

            # Evaluate condition
            condition_result = eval_salary_formula(condition_expr, variables)
            if condition_result:
                return eval_salary_formula(true_expr, variables), None
            else:
                return eval_salary_formula(false_expr, variables), None

        # ---- 4 Replace variables like B, HRA, SA, etc. ----
        for var, val in variables.items():
            if isinstance(val, tuple):
                val = val[0]
            formula = re.sub(rf"\b{var}\b", str(val or 0), formula)
            
        
        # ---- 5 Final cleanup before eval ----
        formula = formula.replace("₹", "").replace(",", "").strip()
        
        frappe.logger().info(f"[Salary Eval] Final Clean Formula: {formula}")

        # ---- 6 Evaluate safely ----
        evaluated_value = eval_salary_formula(formula, variables)
        return float(evaluated_value or 0), None

    except Exception as e:
        return None, f"Error evaluating formula '{formula}': {str(e)}"


# Helper Function for Safe Evaluation
def eval_salary_formula(formula, variables):
    """Safely evaluate formula using frappe.safe_eval with fallback."""
    try:
        return frappe.safe_eval(formula, None, variables)
    except Exception:
        # Try with Python eval as fallback
        try:
            return eval(formula, {"__builtins__": {}}, variables)
        except Exception:
            return 0
        
# ? Find Salary Component "B" or fallback to "B_1"
def find_salary_component(self):
    salary_slip_doc = frappe.get_doc("Salary Slip", self.name)

    # First: try exact "B"
    for table in [salary_slip_doc.earnings, salary_slip_doc.deductions]:
        for item in table:
            if item.salary_component and item.abbr == "B":
                return item.salary_component, item.amount, item.abbr

    # Second: fallback to "B_1"
    for table in [salary_slip_doc.earnings, salary_slip_doc.deductions]:
        for item in table:
            if item.salary_component and item.abbr == "B_1":
                return item.salary_component, item.amount, item.abbr

    return None, 0, None
