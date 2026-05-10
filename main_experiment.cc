#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
//#include "ns3/netanim-module.h"

using namespace ns3;

// Global variables for metrics and tracking
Time slowStartEndTime = Seconds(0);
uint32_t lastTotalRxBytes = 0;
double throughputInterval = 0.1; // 100ms interval for TPUT tracking

static void
CwndTracer(uint32_t oldCwnd, uint32_t newCwnd)
{
    // Output format: CWND [Time] [WindowSizeInBytes]
    std::cout << "CWND\t" << Simulator::Now().GetSeconds() << "\t" << newCwnd << std::endl;

    // Logic to detect when Slow-Start ends (window stops doubling or loss occurs)
    if (slowStartEndTime == Seconds(0) && newCwnd <= oldCwnd + 536 && oldCwnd > 2000) {
        slowStartEndTime = Simulator::Now();
    }
}

static void
CalculateThroughput(Ptr<PacketSink> sink)
{
    double timeNow = Simulator::Now().GetSeconds();
    uint32_t totalRxBytes = sink->GetTotalRx();
    
    // Instantaneous Throughput calculation (Mbps)
    double curThroughput = (totalRxBytes - lastTotalRxBytes) * 8.0 / (throughputInterval * 1e6);
    
    // Output format: TPUT [Time] [Mbps]
    std::cout << "TPUT\t" << timeNow << "\t" << curThroughput << std::endl;
    
    lastTotalRxBytes = totalRxBytes;
    
    // Schedule the next measurement check
    Simulator::Schedule(Seconds(throughputInterval), &CalculateThroughput, sink);
}

int main(int argc, char *argv[])
{
    // Default delay, overridden by command line arguments
    std::string delay = "1ms"; 
    CommandLine cmd;
    cmd.AddValue("delay", "Delay of the link (e.g., 1ms, 50ms, 300ms)", delay);
    cmd.Parse(argc, argv);

    // Explicitly set TCP NewReno for academic benchmarking
    Config::SetDefault("ns3::TcpL4Protocol::SocketType", StringValue("ns3::TcpNewReno"));

    NodeContainer nodes;
    nodes.Create(2);

    // Configure the Point-to-Point link (Standard 10Mbps reference)
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("10Mbps"));
    p2p.SetChannelAttribute("Delay", StringValue(delay));

    NetDeviceContainer devices = p2p.Install(nodes);

    // Error Model: Simulates random packet loss (0.0000001% rate)
    Ptr<RateErrorModel> em = CreateObject<RateErrorModel>();
    em->SetAttribute("ErrorRate", DoubleValue(0.0000001)); // test 0%
    devices.Get(1)->SetAttribute("ReceiveErrorModel", PointerValue(em));

    InternetStackHelper stack;
    stack.Install(nodes);

    Ipv4AddressHelper address;
    address.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign(devices);

    // Setup Packet Sink (The Receiver)
    uint16_t port = 9;
    PacketSinkHelper sinkHelper("ns3::TcpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
    ApplicationContainer sinkApp = sinkHelper.Install(nodes.Get(1));
    sinkApp.Start(Seconds(0.0));
    sinkApp.Stop(Seconds(30.0));

    // Setup BulkSend (The Sender - saturates the link)
    BulkSendHelper source("ns3::TcpSocketFactory", InetSocketAddress(interfaces.GetAddress(1), port));
    source.SetAttribute("MaxBytes", UintegerValue(0)); 
    ApplicationContainer sourceApp = source.Install(nodes.Get(0));
    sourceApp.Start(Seconds(1.0));
    sourceApp.Stop(Seconds(30.0));

    // Schedule the Throughput Calculator after connection establishment
    Ptr<PacketSink> sink = DynamicCast<PacketSink>(sinkApp.Get(0));
    Simulator::Schedule(Seconds(1.1), &CalculateThroughput, sink);

    // Trace the Congestion Window on Node 0
    Simulator::Schedule(Seconds(1.0001), []() {
        Config::ConnectWithoutContext("/NodeList/0/$ns3::TcpL4Protocol/SocketList/0/CongestionWindow", MakeCallback(&CwndTracer));
    });

    // Install FlowMonitor to gather global stats
    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();

    Simulator::Stop(Seconds(30.0));
    // AnimationInterface anim ("topology.xml");
    // anim.SetConstantPosition(nodes.Get(0), 10.0, 50.0);
    // anim.SetConstantPosition(nodes.Get(1), 80.0, 50.0);
    Simulator::Run();

    // Final Performance Metrics Output
    std::map<FlowId, FlowMonitor::FlowStats> stats = monitor->GetFlowStats();
    for (auto const& [key, val] : stats) {
        // Label flow types to distinguish data from ACKs
        std::string flowType = (val.rxBytes > 100000) ? "DATA FLOW" : "ACK FLOW";
        
        std::cout << "\n--- " << flowType << " ---" << std::endl;
        std::cout << "Avg Throughput: " << val.rxBytes * 8.0 / (val.timeLastRxPacket.GetSeconds() - val.timeFirstTxPacket.GetSeconds()) / 1e6 << " Mbps" << std::endl;
        
        // Jitter calculation 
        if (val.rxPackets > 1) {
            std::cout << "Average Jitter: " << (val.jitterSum.GetSeconds() / (val.rxPackets - 1)) * 1000 << " ms" << std::endl;
        } else {
            std::cout << "Average Jitter: 0 ms" << std::endl;
        }

        if (flowType == "DATA FLOW") {
            std::cout << "Slow-Start Ended: " << slowStartEndTime.GetSeconds() << " s" << std::endl;
            std::cout << "Total Packets Rx: " << val.rxPackets << std::endl;
        }
    }

    Simulator::Destroy();
    return 0;
}