def solve_winlinze(grid):
    def win(g):
        if any(
            g[i][0] == g[i][1] == g[i][2] == g[i][3] == g[i][4] != 0 for i in range(5)
        ):
            return True
        if any(
            g[0][j] == g[1][j] == g[2][j] == g[3][j] == g[4][j] != 0 for j in range(5)
        ):
            return True
        if g[0][0] == g[1][1] == g[2][2] == g[3][3] == g[4][4] != 0:
            return True
        if g[0][4] == g[1][3] == g[2][2] == g[3][1] == g[4][0] != 0:
            return True
        return False

    pieces = [(r, c) for r in range(5) for c in range(5) if grid[r][c] != 0]
    empty = [(r, c) for r in range(5) for c in range(5) if grid[r][c] == 0]

    for r1, c1 in pieces:
        for r2, c2 in empty:
            color = grid[r1][c1]
            grid[r2][c2] = color
            grid[r1][c1] = 0
            try:
                if win(grid):
                    return ((r1, c1), (r2, c2))
            finally:
                grid[r1][c1] = color
                grid[r2][c2] = 0

    return None
