import StringIO, sys, os
import libpry
from libpathod import rparse

rparse.TESTING = True


class Sponge:
    def __getattr__(self, x):
        return Sponge()

    def __call__(self, *args, **kwargs):
        pass


class DummyRequest(StringIO.StringIO):
    connection = Sponge()
    def write(self, d, callback=None):
        StringIO.StringIO.write(self, d)
        if callback:
            callback()

    def finish(self):
        return


class uMisc(libpry.AutoTree):
    def test_generators(self):
        v = rparse.Value.parseString("'val'")[0]
        g = v.get_generator({})
        assert g[:] == "val"

    def test_randomgenerator(self):
        g = rparse.RandomGenerator("one", 100)
        assert len(g[:10]) == 10
        assert len(g[1:10]) == 9
        assert len(g[:1000]) == 100
        assert len(g[1000:1001]) == 0
        assert g[0]

    def test_literalgenerator(self):
        g = rparse.LiteralGenerator("one")
        assert g == "one"
        assert g[:] == "one"
        assert g[1] == "n"

    def test_filegenerator(self):
        t = self.tmpdir()
        path = os.path.join(t, "foo")
        f = open(path, "w")
        f.write("x"*10000)
        f.close()
        g = rparse.FileGenerator(path)
        assert len(g) == 10000
        assert g[0] == "x"
        assert g[-1] == "x"
        assert g[0:5] == "xxxxx"

    def test_valueliteral(self):
        v = rparse.ValueLiteral("foo")
        assert v.expr()
        assert str(v)

    def test_file_value(self):
        v = rparse.Value.parseString("<'one two'")[0]
        assert str(v)
        assert v.path == "one two"

        v = rparse.Value.parseString("<path")[0]
        assert v.path == "path"

        t = self.tmpdir()
        p = os.path.join(t, "path")
        f = open(p, "w")
        f.write("x"*10000)
        f.close()

        assert v.get_generator(dict(staticdir=t))

        v = rparse.Value.parseString("<path2")[0]
        libpry.raises(rparse.ServerError, v.get_generator, dict(staticdir=t))
        libpry.raises("no static directory", v.get_generator, dict())

    def test_generated_value(self):
        v = rparse.Value.parseString("!10b")[0]
        assert v.usize == 10
        assert v.unit == "b"
        assert v.bytes() == 10
        v = rparse.Value.parseString("!10")[0]
        assert v.unit == "b"
        v = rparse.Value.parseString("!10k")[0]
        assert v.bytes() == 10240
        v = rparse.Value.parseString("!10g")[0]
        assert v.bytes() == 1024**3 * 10

        v = rparse.Value.parseString("!10g-digits")[0]
        assert v.datatype == "digits"
        g = v.get_generator({})
        assert g[:100]

        v = rparse.Value.parseString("!10-digits")[0]
        assert v.unit == "b"
        assert v.datatype == "digits"

    def test_value(self):
        assert rparse.Value.parseString("'val'")[0].val == "val"
        assert rparse.Value.parseString('"val"')[0].val == "val"
        assert rparse.Value.parseString('"\'val\'"')[0].val == "'val'"

    def test_body(self):
        e = rparse.Body.expr()
        v = e.parseString("b'foo'")[0]
        assert v.value.val == "foo"

        v = e.parseString("b!100")[0]
        assert str(v.value) == "!100b-bytes"

        v = e.parseString("b!100g-digits", parseAll=True)[0]
        assert v.value.datatype == "digits"
        assert str(v.value) == "!100g-digits"

    def test_header(self):
        e = rparse.Header.expr()
        v = e.parseString("h'foo'='bar'")[0]
        assert v.key.val == "foo"
        assert v.value.val == "bar"

    def test_code(self):
        e = rparse.Code.expr()
        v = e.parseString("200")[0]
        assert v.code == 200

        v = e.parseString("404'msg'")[0]
        assert v.code == 404
        assert v.msg.val == "msg"

        r = e.parseString("200'foo'")[0]
        assert r.msg.val == "foo"

        r = e.parseString("200'\"foo\"'")[0]
        assert r.msg.val == "\"foo\""

        r = e.parseString('200"foo"')[0]
        assert r.msg.val == "foo"

        r = e.parseString('404')[0]
        assert r.msg.val == "Not Found"

        r = e.parseString('10')[0]
        assert r.msg.val == "Unknown code"

    def test_internal_response(self):
        d = DummyRequest()
        s = rparse.InternalResponse(400, "foo")
        s.render(d)


class uDisconnects(libpry.AutoTree):
    def test_parse(self):
        assert (0, "disconnect") in rparse.parse({}, "400:db").actions
        assert ("random", "disconnect") in rparse.parse({}, "400:dr").actions

    def test_before(self):
        e = rparse.DisconnectBefore.expr()
        v = e.parseString("db")[0]
        assert isinstance(v, rparse.DisconnectBefore)

        v = e.parseString("db")[0]
        assert isinstance(v, rparse.DisconnectBefore)

    def test_random(self):
        e = rparse.DisconnectRandom.expr()
        v = e.parseString("dr")[0]
        assert isinstance(v, rparse.DisconnectRandom)

        v = e.parseString("dr")[0]
        assert isinstance(v, rparse.DisconnectRandom)


class uShortcutContentType(libpry.AutoTree):
    def test_parse(self):
        assert len(rparse.parse({}, "400:c'foo'").headers) == 1


class uPauses(libpry.AutoTree):
    def test_before(self):
        e = rparse.PauseBefore.expr()
        v = e.parseString("pb10")[0]
        assert v.value == 10

        v = e.parseString("pbforever")[0]
        assert v.value == "forever"

    def test_after(self):
        e = rparse.PauseAfter.expr()
        v = e.parseString("pa10")[0]
        assert v.value == 10

    def test_random(self):
        e = rparse.PauseRandom.expr()
        v = e.parseString("pr10")[0]
        assert v.value == 10


class uparse(libpry.AutoTree):

    def test_parse_err(self):
        libpry.raises(rparse.ParseException, rparse.parse, {}, "400:msg,b:")
        try:
            rparse.parse({}, "400'msg':b:")
        except rparse.ParseException, v:
            assert v.marked()
            assert str(v)

    def test_parse_header(self):
        r = rparse.parse({}, '400:h"foo"="bar"')
        assert r.get_header("foo") == "bar"

    def test_parse_pause_before(self):
        r = rparse.parse({}, "400:pb10")
        assert (0, "pause", 10) in r.actions

    def test_parse_pause_after(self):
        r = rparse.parse({}, "400:pa10")
        assert (sys.maxint, "pause", 10) in r.actions

    def test_parse_pause_random(self):
        r = rparse.parse({}, "400:pr10")
        assert ("random", "pause", 10) in r.actions


class uResponse(libpry.AutoTree):
    def dummy_response(self):
        return rparse.parse({}, "400'msg'")

    def test_response(self):
        r = rparse.parse({}, "400'msg'")
        assert r.code == 400
        assert r.msg == "msg"

        r = rparse.parse({}, "400'msg':b!100b")
        assert r.msg == "msg"
        assert r.body[:]
        assert str(r)

    def test_ready_randoms(self):
        r = rparse.parse({}, "400'msg'")

        x = [(0, 5)]
        assert r.ready_randoms(100, x) == x

        x = [("random", 5)]
        ret = r.ready_randoms(100, x)
        assert 0 <= ret[0][0] < 100

        x = [(1, 5), (0, 5)]
        assert r.ready_randoms(100, x) == sorted(x)

    def test_write_values_disconnects(self):
        r = self.dummy_response()
        s = DummyRequest()
        tst = "foo"*100
        r.write_values(s, [tst], [(0, "disconnect")], blocksize=5)
        assert not s.getvalue()

    def test_write_values(self):
        tst = "foo"*1025
        r = rparse.parse({}, "400'msg'")

        s = DummyRequest()
        r.write_values(s, [tst], [])
        assert s.getvalue() == tst

    def test_write_values_pauses(self):
        tst = "".join(str(i) for i in range(10))
        r = rparse.parse({}, "400'msg'")

        for i in range(2, 10):
            s = DummyRequest()
            r.write_values(s, [tst], [(2, "pause", 0), (1, "pause", 0)], blocksize=i)
            assert s.getvalue() == tst

        for i in range(2, 10):
            s = DummyRequest()
            r.write_values(s, [tst], [(1, "pause", 0)], blocksize=i)
            assert s.getvalue() == tst

        tst = ["".join(str(i) for i in range(10))]*5
        for i in range(2, 10):
            s = DummyRequest()
            r.write_values(s, tst[:], [(1, "pause", 0)], blocksize=i)
            assert s.getvalue() == "".join(tst)

    def test_render(self):
        s = DummyRequest()
        r = rparse.parse({}, "400'msg'")
        r.render(s)

    def test_length(self):
        def testlen(x):
            s = DummyRequest()
            x.render(s)
            assert x.length() == len(s.getvalue())
        testlen(rparse.parse({}, "400'msg'"))
        testlen(rparse.parse({}, "400'msg':h'foo'='bar'"))
        testlen(rparse.parse({}, "400'msg':h'foo'='bar':b!100b"))


tests = [
    uResponse(),
    uPauses(),
    uDisconnects(),
    uMisc(),
    uparse(),
    uShortcutContentType()
]