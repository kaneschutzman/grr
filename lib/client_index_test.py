#!/usr/bin/env python
"""Tests for grr.lib.client_index."""


from grr.lib import aff4
from grr.lib import client_index
from grr.lib import flags
from grr.lib import test_lib
from grr.lib import utils
from grr.lib.rdfvalues import client as rdf_client

CLIENT_ID = "C.00aaeccbb45f33a3"


class ClientIndexTest(test_lib.AFF4ObjectTest):

  def testClientIdToFromURN(self):
    index = aff4.FACTORY.Create("aff4:/client-index/",
                                aff4_type="ClientIndex",
                                mode="rw",
                                token=self.token)
    # Capitilzation is fixed if necessary.
    self.assertEqual(
        CLIENT_ID,
        index._ClientIdFromURN(
            rdf_client.ClientURN("aff4:/C.00AAeccbb45f33a3")))
    self.assertEqual(rdf_client.ClientURN("aff4:/C.00aaeccbb45f33a3"),
                     index._URNFromClientID(CLIENT_ID))

  def testAnalyzeClient(self):
    index = aff4.FACTORY.Create("aff4:/client-index/",
                                aff4_type="ClientIndex",
                                mode="rw",
                                token=self.token)
    test_lib.ClientFixture("aff4:/" + CLIENT_ID, token=self.token)
    client = aff4.FACTORY.Create("aff4:/" + CLIENT_ID,
                                 aff4_type="VFSGRRClient",
                                 mode="rw",
                                 token=self.token)
    _, keywords = index.AnalyzeClient(client)

    # Should not contain an empty string.
    self.assertNotIn("", keywords)

    # OS of the client
    self.assertIn("windows", keywords)

    # Users of the client.
    self.assertIn("bert", keywords)
    self.assertIn("bertrand", keywords)
    self.assertNotIn(")", keywords)
    self.assertIn("russell", keywords)
    self.assertIn("logician", keywords)
    self.assertIn("ernie", keywords)
    self.assertIn("eric", keywords)
    self.assertIn("jacobson", keywords)
    self.assertIn("steve o'bryan", keywords)
    self.assertIn("o'bryan", keywords)

    # Client information.
    self.assertIn("grr monitor", keywords)
    self.assertIn("client-label-23", keywords)

  def testAddLookupClients(self):
    index = aff4.FACTORY.Create("aff4:/client-index1/",
                                aff4_type="ClientIndex",
                                mode="rw",
                                token=self.token)
    client_urns = self.SetupClients(42)
    for urn in client_urns:
      client = aff4.FACTORY.Create(urn,
                                   aff4_type="VFSGRRClient",
                                   mode="r",
                                   token=self.token)
      index.AddClient(client)

    # Check unique identifiers.
    self.assertEqual(
        index.LookupClients(["192.168.0.1"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])
    self.assertEqual(
        index.LookupClients(["2001:aBcd::1"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])
    self.assertEqual(
        index.LookupClients(["ip:192.168.0.1"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])
    self.assertEqual(
        index.LookupClients(["ip:2001:abcd::1"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])
    self.assertEqual(
        index.LookupClients(["host-2"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000002")])
    self.assertEqual(
        index.LookupClients(["C.1000000000000002"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000002")])
    self.assertEqual(
        index.LookupClients(["aabbccddee01"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])
    self.assertEqual(
        index.LookupClients(["mac:aabbccddee01"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])
    self.assertEqual(
        index.LookupClients(["aa:bb:cc:dd:ee:01"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])
    self.assertEqual(
        index.LookupClients(["mac:aa:bb:cc:dd:ee:01"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000001")])

    # IP prefixes of octets should work:
    self.assertEqual(
        sorted(index.LookupClients(["192.168.0"])), sorted(client_urns))

    # Hostname prefixes of tokens should work.
    self.assertEqual(
        index.LookupClients(["host-5.example"]),
        [rdf_client.ClientURN("aff4:/C.1000000000000005")])

    # Intersections should work.
    self.assertEqual(index.LookupClients(["192.168.0", "Host-2"]),
                     [rdf_client.ClientURN("aff4:/C.1000000000000002")])

    # Universal keyword should find everything.
    self.assertEqual(len(index.LookupClients(["."])), 42)

  def testAddTimestamp(self):
    index = aff4.FACTORY.Create("aff4:/client-index2/",
                                aff4_type="ClientIndex",
                                mode="rw",
                                token=self.token)

    client_urns = self.SetupClients(5)
    # 1413807132 = Mon, 20 Oct 2014 12:12:12 GMT
    with test_lib.FakeTime(1413807132):
      for urn in client_urns:
        client = aff4.FACTORY.Create(urn,
                                     aff4_type="VFSGRRClient",
                                     mode="r",
                                     token=self.token)
        index.AddClient(client)

    self.assertEqual(len(index.LookupClients([".", "start_date:2014-10-20"])),
                     5)
    self.assertEqual(len(index.LookupClients([".", "start_date:2014-10-21"])),
                     0)
    self.assertEqual(len(index.LookupClients([".", "start_date:2013-10-20",
                                              "end_date:2014-10-19"])), 0)
    self.assertEqual(len(index.LookupClients([".", "start_date:2013-10-20",
                                              "end_date:2014-10-20"])), 5)

    # Ignore the keyword if the date is not readable.
    self.assertEqual(len(index.LookupClients([".", "start_date:2013-10-20",
                                              "end_date:XXXX"])), 5)

  def testUnversionedKeywords(self):
    index = aff4.FACTORY.Create("aff4:/client-index3/",
                                aff4_type="ClientIndex",
                                mode="rw",
                                token=self.token)

    client_urns = self.SetupClients(5)

    with test_lib.FakeTime(1000000):
      for i in range(5):
        client = aff4.FACTORY.Create(client_urns[i],
                                     aff4_type="VFSGRRClient",
                                     mode="rw",
                                     token=self.token)
        client.Set(client.Schema.HOST_IPS("10.1.0.%d" % i))
        client.Flush()
        index.AddClient(client)

    with test_lib.FakeTime(2000000):
      for i in range(5):
        client = aff4.FACTORY.Create(client_urns[i],
                                     aff4_type="VFSGRRClient",
                                     mode="rw",
                                     token=self.token)
        client.Set(client.Schema.HOST_IPS("10.1.1.%d" % i))
        client.Flush()
        index.AddClient(client)
    with test_lib.FakeTime(3000000):
      self.assertEqual(index.LookupClients(["10.1.0", "Host-2"]),
                       [rdf_client.ClientURN("aff4:/C.1000000000000002")])
      self.assertEqual(index.LookupClients(["+10.1.0", "Host-2"]), [])
      self.assertEqual(index.LookupClients(["+10.1.1", "Host-2"]),
                       [rdf_client.ClientURN("aff4:/C.1000000000000002")])

  def _HostsHaveLabel(self, hosts, label, label_index):
    urns = label_index.FindUrnsByLabel(label)
    result = [utils.SmartStr(c.Get("Host")).lower()
              for c in aff4.FACTORY.MultiOpen(urns, token=self.token)]
    self.assertItemsEqual(hosts, result)

  def testBulkLabelClients(self):
    index = aff4.FACTORY.Create("aff4:/client-index4/",
                                aff4_type="ClientIndex",
                                mode="rw",
                                token=self.token)

    client_urns = self.SetupClients(2)
    for urn in client_urns:
      client = aff4.FACTORY.Create(urn,
                                   aff4_type="VFSGRRClient",
                                   mode="rw",
                                   token=self.token)
      client.AddLabels("test_client", token=self.token)
      client.Flush()
      index.AddClient(client)
    label_index = aff4.FACTORY.Open("aff4:/index/labels/clients",
                                    token=self.token)

    # No hostname.
    client_index.BulkLabel("label-0", ["host-3"], self.token, index)
    self._HostsHaveLabel([], "label-0", label_index)

    # Add label.
    hosts = ["host-0", "host-1"]
    client_index.BulkLabel("label-0", hosts, self.token, index)
    self._HostsHaveLabel(hosts, "label-0", label_index)

    # Add another label only changes the new host.
    hosts = ["host-1"]
    client_index.BulkLabel("label-1", hosts, self.token, index)
    self._HostsHaveLabel(hosts, "label-1", label_index)
    # and other labels remain unchanged.
    hosts = ["host-0", "host-1"]
    self._HostsHaveLabel(hosts, "label-0", label_index)

    # Relabeling updates the label on already labeled hosts.
    hosts = ["host-0"]
    client_index.BulkLabel("label-0", hosts, self.token, index)
    self._HostsHaveLabel(hosts, "label-0", label_index)
    # and other labels remain unchanged.
    hosts = ["host-1"]
    self._HostsHaveLabel(hosts, "label-1", label_index)


def main(argv):
  test_lib.main(argv)

if __name__ == "__main__":
  flags.StartMain(main)
