import unittest

from scripts.kra_results_crawler import (
    extract_race_keys_from_daily,
    parse_horse_results,
    parse_payouts,
    parse_race_meta,
)


DETAIL_HTML_FIXTURE = """
<table>
<!--<caption>경주정보중 경주일자, 경주번호 ...</caption>-->
<tr class="alignC">
    <td class="bgnone" colspan="4">2026년 04월 19일 (일) 제1경주 서울</td>
    <td class="bgnone">제 31일</td>
    <td class="bgnone">맑음</td>
    <td class="bgnone">건조</td>
    <td class="bgnone">4%</td>
    <td class="bgnone">10:35</td>
</tr>
<tr class="alignC">
    <td>국6등급 </td>
    <td>1200M</td>
    <td>별정A</td>
    <td>일반</td>
    <td colspan="2">R0~0</td>
    <td colspan="2">연령오픈 성별오픈</td>
    <td></td>
</tr>
</table>

<table>
<caption>경주상세성적을 순위, 마번 ... 제공하는 표</caption>
<thead>
<tr>
    <th scope="col">순위</th>
    <th scope="col">마번</th>
    <th scope="col">마명</th>
    <th scope="col">산지</th>
    <th scope="col">성별</th>
    <th scope="col">연령</th>
    <th scope="col">중량</th>
    <th scope="col">레이팅</th>
    <th scope="col">기수명</th>
    <th scope="col">조교사명</th>
    <th scope="col">마주명</th>
    <th scope="col">도착차</th>
    <th scope="col">마체중</th>
    <th scope="col">단승</th>
    <th scope="col">연승</th>
    <th scope="col">장구현황</th>
</tr>
</thead>
<tbody>
<tr>
    <td>1</td><td>2</td><td>라스트케이</td><td>한</td><td>수</td><td>3세</td><td>57</td><td></td>
    <td>장추열</td><td>우창구</td><td>강경운</td><td></td><td>477(-5)</td><td>11.5</td><td>2.7</td><td></td>
</tr>
<tr>
    <td>2</td><td>6</td><td>이끌림</td><td>한</td><td>거</td><td>3세</td><td>57</td><td></td>
    <td>이혁</td><td>정호익</td><td>손병철</td><td>1½</td><td>479(3)</td><td>1.4</td><td>1.1</td><td>계란형큰,망사눈</td>
</tr>
</tbody>
</table>

<table>
<caption>배당률의 정보를 제공하는 표</caption>
<tbody>
<tr>
    <th rowspan="4">배당률</th>
    <td class="textLeft">단승식: ② 11.5 </td>
    <td class="textLeft">연승식: ② 2.7 ⑥ 1.1 ① 1.5 </td>
</tr>
<tr class="case">
    <td class="textLeft">복승식: ②⑥ 8.1 </td>
    <td class="textLeft">쌍승식: ②⑥ 29.0 </td>
</tr>
<tr class="case">
    <td class="textLeft">복연승식: ②⑥ 3.5 ②① 6.9 ⑥① 1.6 </td>
    <td class="textLeft">삼복승식: ②⑥① 9.4 </td>
</tr>
<tr class="case">
    <td class="textLeft">삼쌍승식: ②⑥① 139.7 </td>
    <td>&nbsp;</td>
</tr>
</tbody>
</table>
"""


class TestKraCrawlerParsing(unittest.TestCase):
    def test_extract_race_keys_from_daily(self):
        daily_html = """
        <a onclick="ScoreDetailPopup('1','20260419','1'); return false;">1R</a>
        <a onclick="ScoreDetailPopup('1','20260419','2'); return false;">2R</a>
        <a onclick="ScoreDetailPopup('1','20260419','2'); return false;">2R duplicate</a>
        """
        keys = extract_race_keys_from_daily(daily_html)
        self.assertEqual(keys, [("1", "20260419", "1"), ("1", "20260419", "2")])

    def test_parse_meta_results_and_payouts(self):
        meta = parse_race_meta(
            DETAIL_HTML_FIXTURE,
            default_meet="서울",
            default_date="2026-04-19",
            default_race_no=1,
        )
        self.assertEqual(meta["race_date"], "2026-04-19")
        self.assertEqual(meta["meet"], "서울")
        self.assertEqual(meta["race_no"], "1")
        self.assertEqual(meta["weather"], "맑음")
        self.assertEqual(meta["track_condition"], "건조")
        self.assertEqual(meta["race_time"], "10:35")

        results = parse_horse_results(DETAIL_HTML_FIXTURE, meta)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].horse_name, "라스트케이")
        self.assertEqual(results[1].rank, "2")
        self.assertEqual(results[1].equipment, "계란형큰,망사눈")

        payouts = parse_payouts(DETAIL_HTML_FIXTURE, meta)
        # 단승1 + 연승3 + 복승1 + 쌍승1 + 복연3 + 삼복1 + 삼쌍1 = 11
        self.assertEqual(len(payouts), 11)
        self.assertTrue(any(p.bet_type == "삼쌍승식" and p.odds == "139.7" for p in payouts))
        self.assertTrue(any(p.bet_type == "복연승식" and p.combination == "⑥①" for p in payouts))


if __name__ == "__main__":
    unittest.main()
