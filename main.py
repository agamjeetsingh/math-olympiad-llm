from solvers import NoFeedback, Feedback
from solvers import Properties

def main():
    problem = r"""Show that if $f$ is a function on rationals, then $f(x+y) = f(x) + f(y) for all rationals $x,y$ implies that $f(x) = cx for any rational constant c."""
    solver = Feedback(problem_statement=problem, properties=Properties(max_verifier_passes=4))
    result = solver.run()
    print(result)

if __name__ == "__main__":
    main()