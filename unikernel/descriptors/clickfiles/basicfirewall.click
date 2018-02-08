
source :: FromDevice(0);
sink   :: ToDevice(1);

c :: Classifier(
    12/0806, // ARP goes to output 0
    12/0800 15/cc, // IP to output 1, only if QoS == 0xcc
    -); // without a match to output 2

// ipf :: IPFilter(allow icmp && len > 300,
//                 drop all);

//ipf :: IPFilter(allow ip tos 0,
//                drop all);

source -> c;
c[0] -> sink;
// c[1] -> CheckIPHeader -> ipf -> sink;
c[1] -> sink;
c[2] -> Print -> Discard;

