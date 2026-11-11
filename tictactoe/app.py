from flask import Flask, render_template, request, jsonify
import random

app = Flask(__name__)

# Game state representation: 3x3 grid with None for empty cells
def create_board():
    return [None] * 9

def check_winner(board):
    """Check if there's a winner. Returns 'X', 'O', or None."""
    # Winning combinations (indices)
    win_combos = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
        [0, 4, 8], [2, 4, 6]              # Diagonals
    ]
    
    for combo in win_combos:
        if board[combo[0]] == board[combo[1]] == board[combo[2]] is not None:
            return board[combo[0]]
    
    return None

def is_draw(board):
    """Check if the game is a draw (no empty cells and no winner)."""
    return all(cell is not None for cell in board)

def reset_game():
    """Reset the game to initial state."""
    return create_board()

def minimax(board, depth, is_maximizing):
    """Minimax algorithm for optimal AI play."""
    winner = check_winner(board)
    if winner == 'O':  # AI wins
        return 10 - depth
    elif winner == 'X':  # Human wins
        return depth - 10
    elif is_draw(board):
        return 0
    
    if is_maximizing:
        best_score = -float('inf')
        for i in range(9):
            if board[i] is None:
                board[i] = 'O'
                score = minimax(board, depth + 1, False)
                board[i] = None
                best_score = max(score, best_score)
        return best_score
    else:
        best_score = float('inf')
        for i in range(9):
            if board[i] is None:
                board[i] = 'X'
                score = minimax(board, depth + 1, True)
                board[i] = None
                best_score = min(score, best_score)
        return best_score

def get_best_move(board):
    """Get the best move for AI using minimax."""
    best_score = -float('inf')
    best_move = None
    
    for i in range(9):
        if board[i] is None:
            board[i] = 'O'
            score = minimax(board, 0, False)
            board[i] = None
            if score > best_score:
                best_score = score
                best_move = i
    
    return best_move

def get_available_moves(board):
    """Get list of available empty cell indices."""
    return [i for i, cell in enumerate(board) if cell is None]

# Flask routes
@app.route('/')
def index():
    """Render the main game page."""
    board = create_board()
    current_player = 'X'  # Human always goes first
    winner = check_winner(board)
    draw = is_draw(board)
    
    return render_template('index.html', board=board, player=current_player, winner=winner, draw=draw)

@app.route('/make_move', methods=['POST'])
def make_move():
    """Handle human move."""
    data = request.json
    move_index = int(data.get('move'))
    current_player = data.get('player')
    
    board = create_board()
    winner = check_winner(board)
    draw = is_draw(board)
    
    if not winner and not draw:
        # Validate move
        if board[move_index] is None:
            board[move_index] = current_player
            new_winner = check_winner(board)
            new_draw = is_draw(board)
            
            # If game continues, AI makes its move
            if not new_winner and not new_draw:
                ai_move = get_best_move(board)
                if ai_move is not None:
                    board[ai_move] = 'O'
            
            return jsonify({
                'board': board,
                'player': 'X' if current_player == 'O' else 'O',
                'winner': new_winner,
                'draw': new_draw
            })
    
    return jsonify({'error': 'Invalid move or game already ended'})

@app.route('/reset')
def reset():
    """Reset the game."""
    board = create_board()
    current_player = 'X'
    winner = check_winner(board)
    draw = is_draw(board)
    
    return jsonify({
        'board': board,
        'player': current_player,
        'winner': winner,
        'draw': draw
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
