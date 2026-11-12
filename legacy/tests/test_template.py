import unittest
from legacy.build_template import build


class TemplateTest(unittest.TestCase):
    def test_network_route_and_instance_dependencies(self):
        template = build()
        resources = template["Resources"]
        self.assertEqual(resources["DefaultRoute"]["Properties"]["DestinationCidrBlock"], "0.0.0.0/0")
        self.assertEqual(resources["DefaultRoute"]["DependsOn"], "Attachment")
        self.assertIn("DefaultRoute", resources["WebInstance"]["DependsOn"])
        interface = resources["WebInstance"]["Properties"]["NetworkInterfaces"][0]
        self.assertTrue(interface["AssociatePublicIpAddress"])
        self.assertEqual(interface["SubnetId"], {"Ref": "Subnet"})

    def test_ingress_and_storage(self):
        resources = build()["Resources"]
        rules = resources["WebSecurityGroup"]["Properties"]["SecurityGroupIngress"]
        self.assertEqual(len(rules), 2)
        self.assertEqual([(r["FromPort"], r["ToPort"]) for r in rules], [(80, 80), (22, 22)])
        self.assertEqual(rules[1]["CidrIp"], {"Ref": "SshCidr"})
        instance = resources["WebInstance"]["Properties"]
        self.assertEqual(instance["InstanceType"], "t3.micro")
        self.assertTrue(instance["BlockDeviceMappings"][0]["Ebs"]["DeleteOnTermination"])
        self.assertEqual(instance["MetadataOptions"]["HttpTokens"], "required")


if __name__ == "__main__":
    unittest.main()
