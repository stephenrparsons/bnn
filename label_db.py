import sqlite3

from labels import Bug, Tickmark, TickmarkNumber


class LabelDB(object):
    def __init__(self, label_db_file='data/labels.db', check_same_thread=True):
        self.conn = sqlite3.connect(label_db_file, check_same_thread=check_same_thread)

    def create_if_required(self):
        # called once to create db
        c = self.conn.cursor()
        try:
            c.execute('''create table images (
                          id integer primary key autoincrement,
                          filename text,
                          complete boolean
                     )''')
            c.execute('''create table bugs (
                          image_id integer,
                          x integer,
                          y integer
                     )''')
            c.execute('''create table tickmarks (
                          image_id integer,
                          x integer,
                          y integer
                     )''')
            c.execute('''create table tickmark_numbers (
                          image_id integer,
                          x integer,
                          y integer,
                          width integer,
                          height integer,
                          tickmark_value integer
                     )''')
        except sqlite3.OperationalError:
            # assume table already exists? clumsy...
            pass

    def has_been_created(self):
        c = self.conn.cursor()
        c.execute("select name from sqlite_master where type='table' AND name='images';")
        return c.fetchone() is not None

    def imgs(self):
        c = self.conn.cursor()
        c.execute('select filename from images')
        return set(map(lambda f: f[0], c.fetchall()))

    def has_labels(self, img):
        img_id = self._id_for_img(img)
        if img_id is None:
            return False
        c = self.conn.cursor()
        c.execute('select bugs.image_id from bugs inner join tickmarks t on bugs.image_id = t.image_id '
                  'inner join tickmark_numbers tn on bugs.image_id = tn.image_id where bugs.image_id=?', (img_id,))
        label = c.fetchone()
        if label is not None:
            return True
        return self.get_complete(img)

    def get_bugs(self, img):
        if not self.has_labels(img):
            return []
        c = self.conn.cursor()
        c.execute('''select b.x, b.y
                 from bugs b join images i on b.image_id = i.id
                 where i.filename=?''', (img,))
        return c.fetchall()

    def get_tickmarks(self, img):
        if not self.has_labels(img):
            return []
        c = self.conn.cursor()
        c.execute('''select t.x, t.y
                 from tickmarks t join images i on t.image_id = i.id
                 where i.filename=?''', (img,))
        return c.fetchall()

    def get_tickmark_numbers(self, img):
        if not self.has_labels(img):
            return []
        c = self.conn.cursor()
        c.execute('''select t.x, t.y, t.width, t.height, t.tickmark_value
                 from tickmark_numbers t join images i on t.image_id = i.id
                 where i.filename=?''', (img,))
        return c.fetchall()

    def set_complete(self, img, complete):
        c = self.conn.cursor()
        c.execute('update images set complete=? where filename=?', (complete, img,))
        self.conn.commit()

    def get_complete(self, img):
        c = self.conn.cursor()
        c.execute('select complete from images where filename=?', (img,))
        complete = c.fetchone()
        if complete is None:
            return False
        else:
            return bool(complete[0])

    def set_labels(self, img, labels, flip=False):
        img_id = self._id_for_img(img)
        if img_id is None:
            img_id = self._create_row_for_img(img)
        else:
            self._delete_labels_for_img_id(img_id)
        self._add_rows_for_labels(img_id, labels, flip_x_y=flip)

    def _id_for_img(self, img):
        c = self.conn.cursor()
        c.execute('select id from images where filename=?', (img,))
        img_id = c.fetchone()
        if img_id is None:
            return None
        else:
            return img_id[0]

    def _create_row_for_img(self, img):
        c = self.conn.cursor()
        c.execute('insert into images (filename, complete) values (?, ?)', (img, False,))
        self.conn.commit()
        return self._id_for_img(img)

    def _delete_labels_for_img_id(self, img_id):
        c = self.conn.cursor()
        c.execute('delete from bugs where image_id=?', (img_id,))
        c.execute('delete from tickmarks where image_id=?', (img_id,))
        c.execute('delete from tickmark_numbers where image_id=?', (img_id,))
        self.conn.commit()

    def _add_rows_for_labels(self, img_id, labels, flip_x_y=False):
        c = self.conn.cursor()
        for label in labels:
            x, y = label
            if flip_x_y:
                x, y = y, x
            if isinstance(label, Bug):
                c.execute('insert into bugs (image_id, x, y) values (?, ?, ?)', (img_id, x, y,))
            elif isinstance(label, Tickmark):
                c.execute('insert into tickmarks (image_id, x, y) values (?, ?, ?)', (img_id, x, y,))
            elif isinstance(label, TickmarkNumber):
                w, h, v = label.width, label.height, label.value
                c.execute('insert into tickmark_numbers (image_id, x, y, width, height, tickmark_value) '
                          'values (?, ?, ?, ?, ?, ?)', (img_id, x, y, w, h, v))
        self.conn.commit()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--label-db', type=str, default='data/labels.db')
    opts = parser.parse_args()
    db = LabelDB(label_db_file=opts.label_db)

    print('\n'.join(db.imgs()))
