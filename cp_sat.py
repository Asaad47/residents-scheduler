"""
Residency On-Call Scheduling using OR-Tools CP-SAT

Modifiable parameters:
    n: number of doctors
    m: number of days in month
    start_day: name of weekday month starts on
    disallowed_pairs: list of (doctor, day_index)
"""

from ortools.sat.python import cp_model


def cp_sat_generate_schedule(n, m, start_day, disallowed_pairs,
                      time_limit=10, num_workers=8, random_seed=None):
    # Map days of week to indices
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    start_idx = days.index(start_day)
    # Identify Friday-Saturday weekend blocks
    weekend_fridays = [d for d in range(m)
                       if (start_idx + d) % 7 == days.index("Friday")
                       and d + 1 < m]
    W = len(weekend_fridays)

    model = cp_model.CpModel()
    # Day assignment variables
    day_vars = [model.NewIntVar(0, n-1, f"day_{d}") for d in range(m)]

    # Boolean indicators for assignments
    b = {}
    for i in range(n):
        for d in range(m):
            b[i, d] = model.NewBoolVar(f"b_{i}_{d}")
            model.Add(day_vars[d] == i).OnlyEnforceIf(b[i, d])
            model.Add(day_vars[d] != i).OnlyEnforceIf(b[i, d].Not())

    # Weekend block indicators
    w = {}
    for i in range(n):
        for k, d in enumerate(weekend_fridays):
            w[i, k] = model.NewBoolVar(f"w_{i}_{k}")
            # w[i,k] == 1 if doctor i covers both days of weekend block k
            model.Add(day_vars[d] == i).OnlyEnforceIf(w[i, k])
            model.Add(day_vars[d+1] == i).OnlyEnforceIf(w[i, k])
            model.Add(day_vars[d] != i).OnlyEnforceIf(w[i, k].Not())

    # 1. No doctor on 4 consecutive days
    for i in range(n):
        for d in range(m-3):
            model.Add(sum(b[i, d+k] for k in range(4)) <= 3)

    # 2a. Weekend coverage: same doctor on Fri & Sat
    for d in weekend_fridays:
        model.Add(day_vars[d] == day_vars[d+1])

    # 2b. Distinct number of weekend doctors = min(n, #weekends)
    weekend_used = []
    for i in range(n):
        var = model.NewBoolVar(f"weekend_used_{i}")
        weekend_used.append(var)
        model.AddMaxEquality(var, [w[i, k] for k in range(W)])
    model.Add(sum(weekend_used) == min(n, W))

    # 3. Disallowed assignments
    for i, d in disallowed_pairs:
        model.Add(day_vars[d] != i)

    # 4a. Fair total assignment counts
    L = m // n
    H = (m + n - 1) // n
    counts = []
    for i in range(n):
        c = sum(b[i, d] for d in range(m))
        model.Add(c >= L)
        model.Add(c <= H)
        counts.append(c)

    # 4b. Every 3n-day window: each doctor at least once
    window_size = 3 * n
    if m >= window_size:
        for i in range(n):
            for d in range(m - window_size + 1):
                model.Add(sum(b[i, d+k] for k in range(window_size)) >= 1)

    # 4c. Fair weekend assignment distribution
    if W > 0:
        Lw = W // n
        Hw = (W + n - 1) // n
        for i in range(n):
            model.Add(sum(w[i, k] for k in range(W)) >= Lw)
            model.Add(sum(w[i, k] for k in range(W)) <= Hw)

    # Solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = num_workers
    if random_seed is not None:
        solver.parameters.random_seed = random_seed

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("No valid schedule found.")

    return [solver.Value(day_vars[d]) for d in range(m)]


examples = [
    {
        "num_doctors": 3,
        "month_length": 30,
        "month_start_day": "Friday",
        "disallowed_pairs": [
            (0, 5), (0, 12), (0, 19), (0,26),
            (2, 2), (2,9), (2,16), (2,23), (2, 4), (2, 11), (2, 18), (2, 25),
            (1, 0), (1,1), (1,28), (1, 29)
            ],
        "valid_schedule": [0, 0,
                           1, 1, 0, 2, 0, 1, 2,
                           0, 0, 0, 2, 2, 1, 1,
                           1, 2, 0, 2, 1, 0, 2,
                           1, 2, 1, 1, 0, 2, 2],
        "invalid_schedule": [0, 0,
                            1, 1, 0, 2, 0, 0, 2,
                            0, 0, 0, 2, 2, 1, 1,
                            1, 2, 0, 2, 0, 1, 2,
                            1, 2, 1, 1, 1, 2, 2]
    },
    {
        "num_doctors": 4,
        "month_length": 30,
        "month_start_day": "Sunday",
        "disallowed_pairs": [
            (0,2), (0,9), (0,16), (0,23),
            (1,4), (1,11), (1,18), (1,25),
            (2,4), (2,11), (2,18), (2,25),
            (3,3), (3,10), (3,17), (3,24)
            ],
        "valid_schedule": [0, 1, 1, 2, 0, 2, 2,
                           3, 2, 3, 0, 3, 1, 1,
                           1, 0, 2, 0, 3, 3, 3,
                           1, 3, 1, 1, 3, 0, 0,
                           2, 2],
        "invalid_schedule": [0, 1, 1, 2, 0, 2, 2,
                           3, 2, 3, 0, 3, 3, 1,
                           1, 0, 2, 0, 3, 1, 3,
                           1, 3, 1, 1, 3, 0, 0,
                           2, 0]
    },
    {
        "num_doctors": 5,
        "month_length": 31,
        "month_start_day": "Sunday",
        "disallowed_pairs": [
            (0,1), (0,8), (0,15), (0,22), (0,29), (0,4), (0,11), (0,18), (0,25),
            (1,0), (1,7), (1,14), (1,21), (1,28), (1,4), (1,11), (1,18), (1,25),
            (2,1), (2,8), (2,15), (2,22), (2,29),
            (3,2), (3,9), (3,16), (3,23), (3,30), (3,3), (3,10), (3,17), (3,24),
            (4,3), (4,10), (4,17), (4,24)
            ],
        "valid_schedule": [0, 1, 2, 1, 3, 2, 2,
                           4, 1, 0, 2, 4, 3, 3,
                           0, 3, 4, 1, 2, 1, 1,
                           2, 3, 4, 0, 4, 0, 0,
                           4, 3, 4],
        "invalid_schedule": [0, 0, 0, 0, 0, 0, 0,
                            1, 1, 1, 1, 1, 1, 1,
                            2, 2, 2, 2, 2, 2, 2,
                            3, 3, 3, 3, 3, 3, 3,
                            4, 4, 4]
    },
]


if __name__ == "__main__": 
    
    i = 2
    n = examples[i]["num_doctors"]
    m = examples[i]["month_length"]
    start_day = examples[i]["month_start_day"]
    disallowed_pairs = examples[i]["disallowed_pairs"]
    schedule = cp_sat_generate_schedule(n, m, start_day, disallowed_pairs)
    print("On-call schedule:", schedule)
    
    # # Example usage
    # n = 3
    # m = 30
    # start_day = "Friday"
    # disallowed_pairs = [
    #     (0, 5), (0, 12), (0, 19), (0, 26),
    #     (2, 2), (2, 9), (2, 16), (2, 23),
    #     (2, 4), (2, 11), (2, 18), (2, 25),
    #     (1, 0), (1, 1), (1, 28), (1, 29),
    # ]
    # schedule = generate_schedule(n, m, start_day, disallowed_pairs)
    # print("On-call schedule:", schedule)
