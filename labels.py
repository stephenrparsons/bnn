class Label:
    """Base class for labels, to be subclassed
    """
    def __init__(self, x, y, canvas_id):
        self.x = x
        self.y = y
        self.canvas_id = canvas_id


class Bug(Label):
    """Bug label
    """
    def __init__(self, x, y, canvas_id):
        super().__init__(x, y, canvas_id)


class Tickmark(Label):
    """Tickmark label for the mark itself, not the numbers
    """
    def __init__(self, x, y, canvas_id):
        super().__init__(x, y, canvas_id)


class TickmarkNumber(Label):
    """Label surrounding the numbers written next to a tickmark
    """
    def __init__(self, x, y, canvas_id, width, height, value, number_canvas_id):
        super().__init__(x, y, canvas_id)
        self.width = width
        self.height = height
        self.value = value
        self.number_canvas_id = number_canvas_id
