Point = tuple[int, int]


def solve_match(grid: list[list[int]]) -> tuple[Point, Point] | None:
    def win(g):
        return (
            g[0][0] == g[0][1] == g[0][2]
            or g[1][0] == g[1][1] == g[1][2]
            or g[2][0] == g[2][1] == g[2][2]
            or g[0][0] == g[1][0] == g[2][0]
            or g[0][1] == g[1][1] == g[2][1]
            or g[0][2] == g[1][2] == g[2][2]
        )

    for i in range(3):
        for j in range(3):
            for dx, dy in ((0, 1), (1, 0)):
                ni, nj = i + dx, j + dy
                if ni < 3 and nj < 3:
                    grid[i][j], grid[ni][nj] = grid[ni][nj], grid[i][j]
                    try:
                        if win(grid):
                            return ((i, j), (ni, nj))
                    finally:
                        grid[i][j], grid[ni][nj] = grid[ni][nj], grid[i][j]
    return None
