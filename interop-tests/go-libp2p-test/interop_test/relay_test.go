package interop_test

import (
	"fmt"
	"testing"

	pb "github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/pb"
	"google.golang.org/protobuf/proto"
)

func TestRelayReserveMessage(t *testing.T) {
	// Create RESERVE message
	msg := &pb.HopMessage{
		Type: pb.HopMessage_RESERVE.Enum(),
	}

	// Serialize
	data, err := proto.Marshal(msg)
	if err != nil {
		t.Fatal(err)
	}

	fmt.Printf("✅ Serialized RESERVE message: %d bytes\n", len(data))
	fmt.Printf("Hex: %x\n", data)

	// Deserialize
	msg2 := &pb.HopMessage{}
	if err := proto.Unmarshal(data, msg2); err != nil {
		t.Fatal(err)
	}

	if msg2.GetType() != pb.HopMessage_RESERVE {
		t.Fatal("Type mismatch")
	}

	fmt.Println("✅ Message round-trip successful")
}

func TestRelayConnectMessage(t *testing.T) {
	// Create CONNECT message with peer info
	peerID := []byte{0x12, 0x20, 0x01, 0x02, 0x03, 0x04}
	addr := []byte{0x04, 0x7f, 0x00, 0x00, 0x01, 0x06, 0x1f, 0x90}

	msg := &pb.HopMessage{
		Type: pb.HopMessage_CONNECT.Enum(),
		Peer: &pb.Peer{
			Id:    peerID,
			Addrs: [][]byte{addr},
		},
	}

	// Serialize
	data, err := proto.Marshal(msg)
	if err != nil {
		t.Fatal(err)
	}

	fmt.Printf("✅ Serialized CONNECT message: %d bytes\n", len(data))
	fmt.Printf("Hex: %x\n", data)

	// Deserialize
	msg2 := &pb.HopMessage{}
	if err := proto.Unmarshal(data, msg2); err != nil {
		t.Fatal(err)
	}

	if msg2.GetType() != pb.HopMessage_CONNECT {
		t.Fatal("Type mismatch")
	}

	if msg2.Peer == nil {
		t.Fatal("Peer is nil")
	}

	fmt.Println("✅ CONNECT message round-trip successful")
}

func TestRelayStatusMessage(t *testing.T) {
	// Create STATUS message
	msg := &pb.HopMessage{
		Type: pb.HopMessage_STATUS.Enum(),
		Status: pb.Status_OK.Enum(),
	}

	// Serialize
	data, err := proto.Marshal(msg)
	if err != nil {
		t.Fatal(err)
	}

	fmt.Printf("✅ Serialized STATUS message: %d bytes\n", len(data))
	fmt.Printf("Hex: %x\n", data)

	// Deserialize
	msg2 := &pb.HopMessage{}
	if err := proto.Unmarshal(data, msg2); err != nil {
		t.Fatal(err)
	}

	if msg2.GetType() != pb.HopMessage_STATUS {
		t.Fatal("Type mismatch")
	}

	if msg2.GetStatus() != pb.Status_OK {
		t.Fatal("Status code mismatch")
	}

	fmt.Println("✅ STATUS message round-trip successful")
}
